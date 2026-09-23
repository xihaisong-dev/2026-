"""Verify saved ablations and produce paired, descriptive comparisons."""
import argparse
import gzip
import json
from pathlib import Path
from statistics import mean

from q1_io import sha, write_json


def collect(folder):
    summary = json.loads((folder / 'summary.json').read_text(encoding='utf-8'))
    if not summary['completed'] or not summary['all_budgets_exhausted']:
        raise ValueError('Incomplete experiment')
    for name, expected in summary['code_sha256'].items():
        if sha((folder / 'source_snapshot' / name).read_bytes()) != expected:
            raise ValueError(f'Source mismatch: {name}')
    for row in summary['runs']:
        run = folder / f"{row['case']}_{row['cores']}cores_seed{row['seed']}_{row['config']}"
        for name, expected in row['artifacts'].items():
            if sha((run / name).read_bytes()) != expected:
                raise ValueError(f'Artifact mismatch: {run / name}')
        result = json.loads(gzip.decompress((run / 'evaluation.json.gz').read_bytes()))
        search = json.loads((run / 'search.json').read_text(encoding='utf-8'))
        if result['makespan'] != row['makespan'] or len(search['evaluations']) != row['evaluations']:
            raise ValueError('Metric mismatch')
        if row['evaluations'] != summary['evaluation_budget'] or not row['budget_exhausted']:
            raise ValueError('Unequal evaluation budget')
    return summary


def compare(rows, before, after):
    a = {(r['case'], r['cores'], r['seed']): r for r in rows if r['config'] == before}
    b = {(r['case'], r['cores'], r['seed']): r for r in rows if r['config'] == after}
    if not a or a.keys() != b.keys():
        raise ValueError('Unmatched experiment keys')
    pairs = [{'case': k[0], 'cores': k[1], 'seed': k[2],
              'before': a[k]['makespan'], 'after': b[k]['makespan'],
              'reduction_percent': 100 * (1-b[k]['makespan']/a[k]['makespan'])} for k in sorted(a)]
    return {'before': before, 'after': after, 'pairs': pairs,
            'wins': sum(p['after'] < p['before'] for p in pairs),
            'ties': sum(p['after'] == p['before'] for p in pairs),
            'losses': sum(p['after'] > p['before'] for p in pairs),
            'mean_paired_reduction_percent': mean(p['reduction_percent'] for p in pairs)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--runs', nargs='+', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--pairs', nargs='+', help='Explicit comparisons: before:after')
    args = p.parse_args()
    summaries = [collect(f) for f in args.runs]
    if len({s['evaluation_budget'] for s in summaries}) != 1:
        raise ValueError('Different budgets')
    if any(s['source_zip_sha256'] != summaries[0]['source_zip_sha256'] for s in summaries):
        raise ValueError('Different inputs')
    inputs = {}
    for summary in summaries:
        for name, value in summary['input_sha256'].items():
            if name in inputs and inputs[name] != value:
                raise ValueError('Conflicting input hashes')
            inputs[name] = value
    rows = [r for s in summaries for r in s['runs']]
    if len({(r['case'], r['cores'], r['seed'], r['config']) for r in rows}) != len(rows):
        raise ValueError('Duplicate experiments')
    pairs = [x.split(':') for x in args.pairs] if args.pairs else [
        ('control', 'local'), ('local', 'local_critical'),
        ('local_critical', 'local_critical_adaptive'), ('local_critical_adaptive', 'full'),
        ('without_local', 'full'), ('without_critical', 'full'), ('without_adaptive', 'full'),
        ('control', 'local_critical'), ('legacy_alns', 'control'), ('legacy_alns', 'local_critical')]
    if any(len(pair) != 2 for pair in pairs):
        p.error('pairs must use before:after')
    comparisons = [compare(rows, a, b) for a, b in pairs]
    output = {'status': 'prototype_descriptive_only', 'runs': len(rows),
              'official_evaluations': sum(r['evaluations'] for r in rows),
              'verified_summaries': {str(f): sha((f/'summary.json').read_bytes()) for f in args.runs},
              'comparisons': comparisons, 'results': rows}
    args.output.mkdir(parents=True, exist_ok=False)
    write_json(args.output / 'comparison.json', output)
    lines = ['# 问题一同预算消融', '',
             f"共 {len(rows)} 次运行，{output['official_evaluations']} 次官方评估。每次 {summaries[0]['evaluation_budget']} 次，包含初解。",
             f"{len({r['case'] for r in rows})} 张图；核数 {sorted({r['cores'] for r in rows})}；种子 {sorted({r['seed'] for r in rows})}（各组合见下表）。仅作探索性描述，不作显著性或全量收益结论。", '',
             '正降幅表示后者更快；均值是逐配对百分比的算术平均，不是总时间之比。', '',
             '| 对照 → 候选 | 胜/平/负 | 平均时间降幅 |', '| --- | ---: | ---: |']
    for c in comparisons:
        lines.append(f"| {c['before']} → {c['after']} | {c['wins']}/{c['ties']}/{c['losses']} | {c['mean_paired_reduction_percent']:.3f}% |")
    configs = list(dict.fromkeys(r['config'] for r in rows))
    lines += ['', '## 完成时间（cycles）', '', '| 图/核数/种子 | ' + ' | '.join(configs) + ' |',
              '| --- | ' + ' | '.join(['---:']*len(configs)) + ' |']
    for case, cores, seed in sorted({(r['case'], r['cores'], r['seed']) for r in rows}):
        values = {r['config']: r['makespan'] for r in rows if (r['case'], r['cores'], r['seed']) == (case, cores, seed)}
        lines.append(f'| {case}/{cores}/{seed} | ' + ' | '.join(str(values.get(c, 'NOT_RUN')) for c in configs) + ' |')
    lines += ['', '共同对照 control 也包含固定粒度探索，与旧 ALNS 不同。相对旧算法的改善不能全部归因于四项开关。',
              '开关效果依赖组合与样本，不能把局部结果推广为全量结论；旧默认行为不变。',
              '计数相等不代表墙钟时间相等。每次耗时、逐候选记录和完整官方时间线均保留在原实验目录。',
              '源码快照及全部产物哈希已核对，压缩评估记录已解析并与汇总指标比对。', '']
    (args.output / 'report.md').write_bytes('\n'.join(lines).encode('utf-8'))
    print('\n'.join(lines[:19]))


if __name__ == '__main__':
    main()
