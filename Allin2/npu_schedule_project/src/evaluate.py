"""Thin adapter around the unmodified contest evaluator (all times in cycles)."""
from __future__ import annotations
import argparse
import gzip
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OFFICIAL = ROOT / 'official'
if str(OFFICIAL) not in sys.path:
    sys.path.insert(0, str(OFFICIAL))
from evaluation_validation import read_evaluation_config
from multicore_cut_evaluate_problem_1 import evaluate_scene_a, read_scene_a_config
from multicore_cut_evaluate_problem_2 import evaluate_scene_b, read_scene_b_config
from multicore_cut_evaluate_problem_3 import evaluate_problem_3, read_cache_config
from singlecore_evaluate import evaluate_singlecore as _single


def read_json(path):
    path = Path(path)
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rt', encoding='utf-8') as f:
        return json.load(f)


def write_json(path, data):
    """Atomically write JSON; gzip is used for complete operation traces."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    if path.suffix == '.gz':
        with gzip.open(temp, 'wt', encoding='utf-8', compresslevel=3) as f:
            json.dump(data, f, ensure_ascii=False, separators=(',', ':'))
    else:
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)


def config_values(config_path=None):
    path = str(config_path or ROOT / 'data' / 'config.txt')
    return read_evaluation_config(path), read_scene_a_config(path), read_scene_b_config(path), read_cache_config(path)


def evaluate_singlecore(graph, config_path=None):
    base, a, _, _ = config_values(config_path)
    return _single(graph, **base, cross_core_wait=a['task_cross_core_wait_cycles'], same_core_wait=a['task_same_core_wait_cycles'])


def evaluate_plan(graph, plan, problem, config_path=None):
    """Return original evaluator result without approximating its simulator."""
    base, a, b, c = config_values(config_path)
    problem = int(problem)
    if problem == 1:
        return evaluate_scene_a(graph, plan, **base, cross_core_wait=a['task_cross_core_wait_cycles'], same_core_wait=a['task_same_core_wait_cycles'])
    if problem == 2:
        return evaluate_scene_b(graph, plan, **base, cross_core_copy_delay=b['cross_core_copy_delay_cycles'])
    if problem == 3:
        return evaluate_problem_3(graph, plan, **base, cross_core_copy_delay=b['cross_core_copy_delay_cycles'], **c)
    raise ValueError('problem must be 1, 2, or 3')


def _executed_task_count(result, plan=None):
    """Count actual nonempty execution tasks; idle core contexts are excluded."""
    if plan is not None:
        if result.get('scene') == 'A':
            return len(set(plan['node_to_subgraph'].values()))
        return sum(bool(order) for order in plan['core_schedules'])
    if result.get('scene') == 'A':
        return len(result.get('step3_by_task', {}))
    return sum(bool(core.get('ops')) for core in result.get('per_core_timeline', []))


def flatten_result(result, *, case='', problem=0, method='', baseline_makespan=None,
                   evaluation_seconds=0.0, solver_seconds=0.0, plan=None):
    """Keep official traffic and the derived physical-DDR estimate separate."""
    m = result['data_movement_bytes']
    c = result.get('cache_stats', {})
    elapsed = result['makespan']
    peaks = result.get('memory_peak_by_core', {})
    out = dict(case=case, problem=int(problem), cores=result['num_cores'], method=method,
               makespan=elapsed, baseline_makespan=baseline_makespan,
               speedup=(baseline_makespan / elapsed if baseline_makespan is not None and elapsed else None),
               original_graph_copy_bytes=m['original_graph_copy_bytes'],
               scheduled_copy_bytes=m['scheduled_copy_bytes'],
               added_copy_bytes=m['added_copy_bytes'],
               partition_added_copy_bytes=m['partition_added_copy_bytes'],
               spill_added_copy_bytes=m['spill_added_copy_bytes'],
               cache_hit_rate=c.get('hit_rate', 0.0), cache_hit_bytes=c.get('hit_bytes', 0),
               cache_miss_bytes=c.get('miss_bytes', 0), cache_hits=c.get('hits', 0),
               cache_accesses=c.get('accesses', 0),
               physical_ddr_bytes_derived=m['scheduled_copy_bytes']-c.get('hit_bytes', 0),
               peak_L1=max((v['L1'] for v in peaks.values()), default=0),
               peak_UB=max((v['UB'] for v in peaks.values()), default=0),
               evaluation_seconds=evaluation_seconds, solver_seconds=solver_seconds,
               official_task_count=result.get('task_count'),
               executed_task_count_derived=_executed_task_count(result, plan),
               subgraph_count=(len(set(plan['node_to_subgraph'].values())) if plan else 1))
    return out


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def create_integrity_manifest():
    paths = sorted((ROOT/'official').glob('*.py')) + sorted((ROOT/'data').glob('*'))
    return {str(p.relative_to(ROOT)).replace('\\','/'): sha256_file(p) for p in paths if p.is_file()}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('graph', type=Path)
    ap.add_argument('--plan', type=Path)
    ap.add_argument('--problem', type=int, choices=(1,2,3), default=1)
    ap.add_argument('--singlecore', action='store_true')
    ap.add_argument('--config', type=Path)
    ap.add_argument('--output', type=Path, required=True)
    args=ap.parse_args(); g=read_json(args.graph); t=time.perf_counter()
    if args.singlecore:
        result=evaluate_singlecore(g,args.config)
    else:
        if not args.plan: ap.error('--plan is required unless --singlecore')
        result=evaluate_plan(g,read_json(args.plan),args.problem,args.config)
    result['input_graph']=args.graph.name
    write_json(args.output,result)
    print(json.dumps(flatten_result(result,case=args.graph.stem,problem=args.problem,evaluation_seconds=time.perf_counter()-t),ensure_ascii=False))

if __name__ == '__main__':
    main()
