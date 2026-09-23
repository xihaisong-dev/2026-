"""固定总官方调用预算：顺序增加特性及完整方案逐项关闭。"""
import argparse
from datetime import datetime
import gzip
import json
from pathlib import Path
import platform
import sys

from q1_io import ROOT, PROCESSED, official, verify, sha, write_json
from q1_experimental import FEATURES, solve_experimental

CONFIGS = {
    'control': [],
    'local': ['local_cost'],
    'local_critical': ['local_cost', 'critical'],
    'local_critical_adaptive': ['local_cost', 'critical', 'adaptive'],
    'full': sorted(FEATURES),
    'without_local': sorted(FEATURES - {'local_cost'}),
    'without_critical': sorted(FEATURES - {'critical'}),
    'without_adaptive': sorted(FEATURES - {'adaptive'}),
    'legacy_alns': None,
    'insertion': ['local_cost', 'critical', 'insertion'],
    'comm_rank': ['local_cost', 'critical', 'comm_rank'],
    'insertion_rank': ['local_cost', 'critical', 'insertion', 'comm_rank'],
    'lookahead': ['local_cost', 'critical', 'insertion', 'comm_rank', 'lookahead'],
}
DEFAULT_CONFIGS = [k for k in CONFIGS if k not in {'legacy_alns', 'insertion', 'comm_rank', 'insertion_rank', 'lookahead'}]
BASE_FEATURES = ['local_cost', 'critical', 'insertion', 'comm_rank']
CONFIGS.update({
    'shared_event_late': BASE_FEATURES + ['partition_guard', 'shared_input', 'region', 'exact_region', 'event_rank', 'chain_joint', 'late_chain'],
    'shared_event': BASE_FEATURES + ['partition_guard', 'shared_input', 'region', 'exact_region', 'event_rank'],
    'shared_event_chain': BASE_FEATURES + ['partition_guard', 'shared_input', 'region', 'exact_region', 'event_rank', 'chain_joint'],
    'shared_phase': BASE_FEATURES + ['partition_guard', 'shared_input', 'region', 'exact_region', 'phase_rank'],
    'shared_exact': BASE_FEATURES + ['partition_guard', 'shared_input', 'region', 'exact_region'],
    'shared_exact_wide': BASE_FEATURES + ['partition_guard', 'shared_input', 'region', 'exact_region', 'wide_region'],
    'shared_exact_uphill': BASE_FEATURES + ['partition_guard', 'shared_input', 'region', 'exact_region', 'uphill_region'],
    'shared_fluid': BASE_FEATURES + ['partition_guard', 'shared_input', 'region', 'fluid_rank'],
    'shared_refine': BASE_FEATURES + ['partition_guard', 'shared_input', 'region', 'boundary_refine'],
    'shared_fluid_refine': BASE_FEATURES + ['partition_guard', 'shared_input', 'region', 'fluid_rank', 'boundary_refine'],
    'shared_region_gap': BASE_FEATURES + ['partition_guard', 'shared_input', 'region', 'region_gap'],
    'shared_region': BASE_FEATURES + ['partition_guard', 'shared_input', 'region'],
    'calibrated': BASE_FEATURES + ['calibrated'],
    'joint_cal': BASE_FEATURES + ['calibrated', 'joint'],
    'budget_joint': BASE_FEATURES + ['calibrated', 'joint', 'budget_adapt'],
    'all_new': BASE_FEATURES + ['calibrated', 'joint', 'budget_adapt', 'ddr'],
    'guarded_joint': BASE_FEATURES + ['guarded_joint'],
    'beam': BASE_FEATURES + ['beam'],
    'partition_guard': BASE_FEATURES + ['partition_guard'],
    'shared_input': BASE_FEATURES + ['partition_guard', 'shared_input'],
    'local_repair': BASE_FEATURES + ['partition_guard', 'local_repair'],
    'shared_repair_move': BASE_FEATURES + ['partition_guard', 'shared_input', 'repair_move'],
})


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cases', nargs='+', default=['case_001', 'case_093', 'case_034'])
    p.add_argument('--cores', nargs='+', type=int, default=[4])
    p.add_argument('--seeds', nargs='+', type=int, default=[0, 1])
    p.add_argument('--evaluations', type=int, default=12)
    p.add_argument('--configs', nargs='+', choices=list(CONFIGS),
                   default=DEFAULT_CONFIGS)
    p.add_argument('--cache-dir', type=Path)
    p.add_argument('--output', type=Path)
    args = p.parse_args()
    if args.evaluations < 1 or any(n < 2 or n > 5 for n in args.cores):
        p.error('evaluations >= 1，核数 2～5')
    for values in (args.cases, args.cores, args.seeds, args.configs):
        if len(set(values)) != len(values):
            p.error('不允许重复实验参数')
    m = verify()
    official()
    from evaluation_validation import read_evaluation_config
    from multicore_cut_evaluate_problem_1 import read_scene_a_config
    config = str(PROCESSED / 'data/config.txt')
    settings, waits = read_evaluation_config(config), read_scene_a_config(config)
    paths = [PROCESSED / 'data' / (c + '.json') for c in args.cases]
    if any(not x.is_file() or x.parent.resolve() != (PROCESSED / 'data').resolve() for x in paths):
        p.error('无效算例名称')
    out = args.output or ROOT / '图表/runs' / (datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '-A-q1-ablation')
    out.mkdir(parents=True, exist_ok=False)
    summary = {'status': 'prototype_ablation', 'completed': False, 'python': platform.python_version(),
               'command': sys.argv, 'configs': {k: CONFIGS[k] for k in args.configs},
               'evaluation_budget': args.evaluations, 'source_zip_sha256': m['source_sha256'],
               'input_sha256': {p.name: sha(p.read_bytes()) for p in paths},
               'code_sha256': {f.name: sha(f.read_bytes()) for f in Path(__file__).parent.glob('*.py')},
               'runs': []}
    write_json(out / 'summary.json', summary)
    snapshot = out / 'source_snapshot'
    snapshot.mkdir()
    for filename, expected in summary['code_sha256'].items():
        content = (Path(__file__).parent / filename).read_bytes()
        if sha(content) != expected:
            raise RuntimeError('源码在启动期间发生变化')
        (snapshot / filename).write_bytes(content)
    for path in paths:
        raw = json.loads(path.read_text(encoding='utf-8-sig'))
        for cores in args.cores:
            for seed in args.seeds:
                for name in args.configs:
                    run = out / f'{path.stem}_{cores}cores_seed{seed}_{name}'
                    run.mkdir()
                    print('START', run.name, flush=True)
                    if name == 'legacy_alns':
                        from q1_solver import Graph, greedy_partition, multilevel, solve
                        graph = Graph(raw, settings, waits)
                        initial = greedy_partition(graph, cores)
                        fallback = {'node_to_subgraph': {str(u): 0 for u in sorted(graph.ops)},
                                    'core_schedules': [[0] if graph.ops else []] + [[] for _ in range(cores-1)]}
                        candidates = [fallback, graph.schedule(initial, cores)[0],
                                      graph.schedule(multilevel(graph, initial, cores), cores)[0]]
                        initial_count = len({json.dumps(x, sort_keys=True) for x in candidates})
                        if args.evaluations < initial_count:
                            raise ValueError('legacy 预算不足以容纳原算法初解')
                        plan, result, stats = solve(graph, cores, budget=args.evaluations-initial_count, seed=seed)
                        stats['budget_exhausted'] = len(stats['evaluations']) == args.evaluations
                    else:
                        plan, result, stats = solve_experimental(raw, settings, waits, cores,
                                                                 args.evaluations, seed, CONFIGS[name], cache_dir=args.cache_dir)
                    write_json(run / 'plan.json', plan)
                    write_json(run / 'search.json', stats)
                    payload = json.dumps(result, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
                    (run / 'evaluation.json.gz').write_bytes(gzip.compress(payload, mtime=0))
                    row = {'case': path.stem, 'cores': cores, 'seed': seed, 'config': name,
                           'makespan': result['makespan'], 'speedup': stats['speedup'],
                           'evaluations': len(stats['evaluations']), 'seconds': stats['elapsed_seconds'],
                           'official_calls': stats.get('official_calls', len(stats['evaluations'])),
                           'cache_hits': stats.get('cache_hits', 0),
                           'budget_exhausted': stats['budget_exhausted'],
                           'artifacts': {f.name: sha(f.read_bytes()) for f in run.iterdir()}}
                    summary['runs'].append(row)
                    write_json(out / 'summary.json', summary)
                    print('DONE', run.name, row['makespan'], f"calls={row['evaluations']}", flush=True)
    summary['completed'] = True
    summary['all_budgets_exhausted'] = all(r['budget_exhausted'] for r in summary['runs'])
    write_json(out / 'summary.json', summary)


if __name__ == '__main__':
    main()
