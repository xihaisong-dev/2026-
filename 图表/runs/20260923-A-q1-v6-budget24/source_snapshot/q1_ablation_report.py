"""Verify saved ablations and produce paired, descriptive comparisons."""
import argparse
import gzip
import json
from pathlib import Path
from statistics import mean

from q1_io import sha, write_json, official, verify, PROCESSED


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
        diagnostics = [e['timing_diagnostic'] for e in search['evaluations'] if 'timing_diagnostic' in e]
        if diagnostics:
            row['prediction_diagnostics'] = {
                'candidate_count': len(diagnostics),
                'mean_absolute_relative_error': mean(abs(d['predicted_makespan']-d['official_makespan'])/max(1,d['official_makespan']) for d in diagnostics),
                'mean_local_residual_cycles': mean(d['local_model_residual'] for d in diagnostics),
                'mean_global_residual_cycles': mean(d['global_replay_residual'] for d in diagnostics),
                'mean_wait_effect_cycles': mean(d['fixed_profile_wait_effect'] for d in diagnostics),
            }
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
    p.add_argument('--bounds', action='store_true', help='Add verified conservative structural bounds')
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
              'evaluated_candidates': sum(r['evaluations'] for r in rows),
              'official_evaluations': sum(r.get('official_calls', r['evaluations']) for r in rows),
              'cache_hits': sum(r.get('cache_hits', 0) for r in rows),
              'verified_summaries': {str(f): sha((f/'summary.json').read_bytes()) for f in args.runs},
              'comparisons': comparisons, 'results': rows}
    if args.bounds:
        verify()
        official()
        from q1_solver import Graph
        from q1_bounds import structural_bound
        from evaluation_validation import read_evaluation_config
        from multicore_cut_evaluate_problem_1 import read_scene_a_config
        config = str(PROCESSED / 'data/config.txt')
        settings, waits = read_evaluation_config(config), read_scene_a_config(config)
        bounds = {}
        for case, cores in sorted({(r['case'], r['cores']) for r in rows}):
            path = PROCESSED / 'data' / (case+'.json')
            if sha(path.read_bytes()) != inputs[path.name]:
                raise ValueError('Bound input mismatch')
            g = Graph(json.loads(path.read_text(encoding='utf-8-sig')), settings, waits)
            bounds[f'{case}/{cores}'] = structural_bound(g, cores)
        output['structural_bounds'] = bounds
        for r in rows:
            lb = bounds[f"{r['case']}/{r['cores']}"]['lower_bound_cycles']
            if r['makespan'] < lb:
                raise ValueError('Reported makespan violates structural bound')
            r['makespan_over_lower_bound'] = r['makespan']/lb if lb else None
    args.output.mkdir(parents=True, exist_ok=False)
    write_json(args.output / 'comparison.json', output)
    lines = ['# 问题一同预算消融', '',
             f"共 {len(rows)} 次运行，{output['evaluated_candidates']} 个已评候选，{output['official_evaluations']} 次实际官方调用，{output['cache_hits']} 次缓存命中。每次候选预算 {summaries[0]['evaluation_budget']}，包含初解与命中。",
             f"{len({r['case'] for r in rows})} 张图；核数 {sorted({r['cores'] for r in rows})}；种子 {sorted({r['seed'] for r in rows})}（各组合见下表）。仅作探索性描述，不作显著性或全量收益结论。", '',
             '正降幅表示后者更快；均值是逐配对百分比的算术平均，不是总时间之比。', '',
             '| 对照 → 候选 | 胜/平/负 | 平均时间降幅 |', '| --- | ---: | ---: |']
    for c in comparisons:
        lines.append(f"| {c['before']} → {c['after']} | {c['wins']}/{c['ties']}/{c['losses']} | {c['mean_paired_reduction_percent']:.3f}% |")
    configs = list(dict.fromkeys(r['config'] for r in rows))
    diagnostic_rows = [r for r in rows if 'prediction_diagnostics' in r]
    if diagnostic_rows:
        lines += ['', '## 候选预测诊断', '', '| 配置 | 平均绝对相对误差 | 局部时长残差均值 cycles | 全局回放残差均值 cycles |',
                  '| --- | ---: | ---: | ---: |']
        for config in configs:
            ds = [r['prediction_diagnostics'] for r in diagnostic_rows if r['config'] == config]
            if ds:
                lines.append(f"| {config} | {100*mean(d['mean_absolute_relative_error'] for d in ds):.3f}% | {mean(d['mean_local_residual_cycles'] for d in ds):.2f} | {mean(d['mean_global_residual_cycles'] for d in ds):.2f} |")
        lines += ['', '各配置访问的候选不同，该误差均值不是同候选校准优劣证明。局部残差包含Pipe依赖、复制和内存约束等，全局回放残差提示并发模型差异；二者不是独立因果归因。原始逐候选诊断见search.json。']
    lines += ['', '## 完成时间（cycles）', '', '| 图/核数/种子 | ' + ' | '.join(configs) + ' |',
              '| --- | ' + ' | '.join(['---:']*len(configs)) + ' |']
    for case, cores, seed in sorted({(r['case'], r['cores'], r['seed']) for r in rows}):
        values = {r['config']: r['makespan'] for r in rows if (r['case'], r['cores'], r['seed']) == (case, cores, seed)}
        lines.append(f'| {case}/{cores}/{seed} | ' + ' | '.join(str(values.get(c, 'NOT_RUN')) for c in configs) + ' |')
    if args.bounds:
        lines += ['', '## 结构下界（不保证可达）', '',
                  '| 图/核数 | 下界 cycles | 已观察最佳时间 | 最佳时间/下界 |', '| --- | ---: | ---: | ---: |']
        for key, b in bounds.items():
            case, cores = key.split('/')
            best = min(r['makespan'] for r in rows if r['case'] == case and r['cores'] == int(cores))
            lb = b['lower_bound_cycles']
            lines.append(f'| {key} | {lb} | {best} | {best/lb:.3f} |' if lb else f'| {key} | 0 | {best} | N/A |')
        lines += ['', '下界忽略新增搬运、溢出和等待等约束；时间/下界不是已证明的次优倍数，也不是保证可获得的优化空间。']
    lines += ['', '共同对照 control 也包含固定粒度探索，与旧 ALNS 不同。相对旧算法的改善不能全部归因于四项开关。',
              '开关效果依赖组合与样本，不能把局部结果推广为全量结论；旧默认行为不变。',
              '计数相等不代表墙钟时间相等。每次耗时、逐候选记录和完整官方时间线均保留在原实验目录。',
              '源码快照及全部产物哈希已核对，压缩评估记录已解析并与汇总指标比对。', '']
    (args.output / 'report.md').write_bytes('\n'.join(lines).encode('utf-8'))
    print('\n'.join(lines[:19]))


if __name__ == '__main__':
    main()
