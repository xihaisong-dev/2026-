"""问题一原型命令行入口：prepare / solve。"""
import argparse
from datetime import datetime
import json
from pathlib import Path
import platform
import sys

from q1_io import ROOT, PROCESSED, prepare, verify, official, sha, write_json


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('prepare', help='无损提取附件并审计全部输入')
    run = sub.add_parser('solve', help='生成并用官方评估器验证问题一方案')
    run.add_argument('--cases', nargs='+', default=['case_001'])
    run.add_argument('--cores', nargs='+', type=int, default=[4])
    run.add_argument('--method', choices=['greedy', 'multilevel', 'alns'], default='alns')
    run.add_argument('--budget', type=int, default=12)
    run.add_argument('--refine-budget', type=int, default=0,
                     help='额外粒度/真实时间线瓶颈优化次数，0 保持初版算法')
    run.add_argument('--seed', type=int, default=0)
    run.add_argument('--block-size', type=int, default=64)
    run.add_argument('--output', type=Path)
    run.add_argument('--experimental', action='store_true')
    run.add_argument('--cache-dir', type=Path, help='Optional hash-verified official result cache')
    run.add_argument('--evaluation-budget', type=int, default=12,
                     help='实验框架的总官方评估次数，包含初解')
    run.add_argument('--features', nargs='*', default=[],
                     choices=['local_cost', 'critical', 'adaptive', 'portfolio', 'insertion', 'comm_rank', 'lookahead', 'calibrated', 'joint', 'budget_adapt', 'ddr'])
    args = parser.parse_args(argv)
    if args.command == 'prepare':
        m = prepare()
        print(f"已审计 {len(m['cases'])} 张图，输入目录：{PROCESSED}")
        return
    if any(c < 1 or c > 5 for c in args.cores) or args.budget < 0 or args.block_size < 1 or args.refine_budget < 0:
        parser.error('核数须在 1～5，budget >= 0，block-size > 0')
    if args.evaluation_budget < 1 or ((args.features or args.cache_dir) and not args.experimental):
        parser.error('evaluation-budget 必须为正；features 需要 experimental')
    manifest = verify()
    official()
    from evaluation_validation import read_evaluation_config
    from multicore_cut_evaluate_problem_1 import read_scene_a_config
    from q1_solver import Graph, solve
    config = PROCESSED / 'data/config.txt'
    settings = read_evaluation_config(str(config))
    waits = read_scene_a_config(str(config))
    cases = sorted((PROCESSED / 'data').glob('case_*.json')) if args.cases == ['all'] else [
        PROCESSED / 'data' / (name.removesuffix('.json') + '.json') for name in args.cases]
    for path in cases:
        if path.parent.resolve() != (PROCESSED / 'data').resolve() or not path.is_file():
            parser.error('无效测试图名称: ' + path.name)
    if len(set(cases)) != len(cases) or len(set(args.cores)) != len(args.cores):
        parser.error('测试图和核数不可重复')
    output = args.output or ROOT / '图表/runs' / (datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '-A-q1')
    output.mkdir(parents=True, exist_ok=False)
    report = {'status': 'prototype', 'command': sys.argv, 'python': platform.python_version(),
              'input_manifest_sha256': sha(json.dumps(manifest, ensure_ascii=False, sort_keys=True).encode('utf-8')),
              'input_manifest_hash_mode': 'canonical JSON: ensure_ascii=False, sort_keys=True',
              'source_sha256': manifest['source_sha256'],
              'code_sha256': {p.name: sha(p.read_bytes()) for p in Path(__file__).parent.glob('*.py')},
              'runs': []}
    write_json(output / 'summary.json', report)
    for path in cases:
        graph = Graph(json.loads(path.read_text(encoding='utf-8-sig')), settings, waits)
        for cores in args.cores:
            prefix = f'{path.stem}_{cores}cores'
            print(f"开始 {prefix} / {'experimental' if args.experimental else args.method}", flush=True)
            def progress(record):
                print(f"  {record['candidate']}: {record['makespan']} cycles "
                      f"({record['evaluation_seconds']:.2f}s)", flush=True)
            if args.experimental:
                from q1_experimental import solve_experimental
                plan, result, stats = solve_experimental(graph.raw, settings, waits, cores,
                    args.evaluation_budget, args.seed, args.features, progress, args.cache_dir)
            else:
                plan, result, stats = solve(graph, cores, args.method, args.budget, args.seed,
                                            args.block_size, on_evaluation=progress,
                                            refine_budget=args.refine_budget)
            write_json(output / (prefix + '_plan.json'), plan)
            write_json(output / (prefix + '_evaluation.json'), result)
            write_json(output / (prefix + '_search.json'), stats)
            report['runs'].append({'case': path.stem, 'cores': cores, 'makespan': result['makespan'],
                                  'speedup': stats['speedup'], 'method': stats['method'],
                                  'evaluation_count': len(stats['evaluations']),
                                  'plan_sha256': sha((output / (prefix + '_plan.json')).read_bytes())})
            write_json(output / 'summary.json', report)
            print(f"完成：{result['makespan']} cycles，单核基准比 {stats['speedup']:.4f}", flush=True)
    report['mean_speedup_by_cores'] = {
        str(c): sum(r['speedup'] for r in report['runs'] if r['cores'] == c) /
        sum(r['cores'] == c for r in report['runs']) for c in args.cores}
    report['completed'] = True
    write_json(output / 'summary.json', report)
    print('结果目录：', output)


if __name__ == '__main__':
    main()
