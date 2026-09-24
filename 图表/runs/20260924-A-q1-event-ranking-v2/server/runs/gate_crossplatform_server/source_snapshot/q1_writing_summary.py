"""Rebuild the writing tables from the frozen 100-case official results."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
from statistics import mean


def main():
    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=root / '图表/runs/20260923-A-q1-v18-analysis/all_case_results.csv')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    rows = list(csv.DictReader(args.source.open(encoding='utf-8-sig', newline='')))
    selected = [r for r in rows if r['config'] in ('fixed_single', 'shared_region')]
    keys = [(r['case'], int(r['cores'])) for r in selected]
    expected = {(f'case_{i:03d}', k) for i in range(1, 101) for k in range(1, 6)}
    if len(keys) != 500 or set(keys) != expected:
        raise ValueError('Expected exactly 100 cases x 5 core counts')
    single = {r['case']: int(r['makespan']) for r in selected if int(r['cores']) == 1}
    tables = []
    for k in range(1, 6):
        subset = [r for r in selected if int(r['cores']) == k]
        speeds = [single[r['case']] / int(r['makespan']) for r in subset]
        best = max(speeds)
        winners = [r['case'] for r, s in zip(subset, speeds) if s == best]
        tables.append(dict(cores=k, cases=100, mean_speedup=mean(speeds),
                           makespan_sum=sum(int(r['makespan']) for r in subset),
                           added_copy_bytes_sum=sum(int(r['added_copy_bytes']) for r in subset),
                           best_speedup=best, best_cases=winners,
                           best_case_makespans={r['case']: int(r['makespan']) for r in subset if r['case'] in winners}))
    args.output.mkdir(parents=True, exist_ok=False)
    with (args.output / 'baseline_500.csv').open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(selected[0]))
        writer.writeheader()
        writer.writerows(sorted(selected, key=lambda r: (r['case'], int(r['cores']))))
    result = dict(source=str(args.source.relative_to(root)) if args.source.is_relative_to(root) else str(args.source),
                  source_sha256=hashlib.sha256(args.source.read_bytes()).hexdigest(),
                  adopted='shared_region', mean_definition='mean_i(T_i1 / T_ik)', rows=500, by_core=tables)
    (args.output / 'summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    text = '# 问题一写作数据表\n\n逐例比值的算术平均；不是总时间之比。采用 shared_region，固定单核整图基准。\n\n'
    text += '| 核数 | 100 图平均加速比 | 最高加速比算例 | 最高加速比 | 该例 Makespan (cycles) |\n|---|---:|---|---:|---:|\n'
    for r in tables:
        winners = '全部 100 图并列' if r['cores'] == 1 else ', '.join(r['best_cases'])
        value = '各图不同' if r['cores'] == 1 else ', '.join(str(v) for v in r['best_case_makespans'].values())
        text += f"| {r['cores']} | {r['mean_speedup']:.6f} | {winners} | {r['best_speedup']:.6f} | {value} |\n"
    text += '\n最优算例按相对各自单核基准的加速比比较。不同图工作量不同，不以绝对最短 cycles 判断算法优劣。\n'
    (args.output / 'tables.md').write_text(text, encoding='utf-8')
    print(json.dumps({'rows': 500, 'mean_speedups': [r['mean_speedup'] for r in tables]}))


if __name__ == '__main__':
    main()
