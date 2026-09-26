"""Portable scene-A baseline entry; standard library only, explicit graph input."""
import argparse
import gzip
import json
import platform
import time
from pathlib import Path
from q1_io import PROCESSED, official, verify, sha, write_json

from q1_ablation import CONFIGS

ADOPTED_POLICY = 'routes_gate_reuse'
BASELINE_FEATURES = tuple(CONFIGS[ADOPTED_POLICY])


def main():
    entry_started = time.perf_counter()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('graph', type=Path)
    parser.add_argument('-n', '--cores', type=int, choices=range(1, 6), required=True)
    parser.add_argument('--config', type=Path, default=PROCESSED / 'data/config.txt')
    parser.add_argument('--output', type=Path, required=True, help='New output directory')
    parser.add_argument('--backend', choices=['official', 'counter'], default='counter')
    parser.add_argument('--budget', type=int, default=12)
    parser.add_argument('--seed', type=int, default=0)
    parser.add_argument('--verify-final', action='store_true',
                        help='Additional original official replay, outside search budget; time is recorded')
    parser.add_argument('--final-check-backend', choices=['official', 'counter'], default='official',
                        help='Experimental counter check is an accelerated replay, not an independent original official replay')
    args = parser.parse_args()
    if args.cores > 1 and args.budget < 8:
        parser.error('Protected baseline partition budget requires --budget >= 8')
    verify()
    mod = official()
    from evaluation_validation import read_evaluation_config, validate_graph
    from q1_experimental import solve_experimental
    raw = json.loads(args.graph.read_text(encoding='utf-8-sig'))
    validate_graph(raw)
    settings = read_evaluation_config(str(args.config))
    waits = mod.read_scene_a_config(str(args.config))
    args.output.mkdir(parents=True, exist_ok=False)
    def phase(name):
        write_json(args.output / 'phase.json', {'phase': name,
            'entry_elapsed_seconds': time.perf_counter() - entry_started,
            'final_check_backend': args.final_check_backend})
        print('PHASE', name, flush=True)
    phase('search_started')
    started = time.perf_counter()
    if args.cores == 1:
        from singlecore_evaluate import build_singlecore_plan
        plan = build_singlecore_plan(raw)
        evaluator = mod.evaluate_scene_a
        if args.backend == 'counter':
            from q1_fast_evaluator import evaluate_scene_a as evaluator
        result = evaluator(raw, plan, settings['bandwidth'], settings['capacity'],
                           waits['task_cross_core_wait_cycles'], waits['task_same_core_wait_cycles'])
        stats = {'evaluations': [], 'evaluation_count': 1,
                 'singlecore_makespan': result['makespan'], 'mode': 'fixed_whole_graph'}
    else:
        def progress(row):
            print(row['candidate'], row['makespan'], flush=True)
        plan, result, stats = solve_experimental(raw, settings, waits, args.cores,
            args.budget, args.seed, BASELINE_FEATURES, on_evaluation=progress,
            evaluator_backend=args.backend)
    solve_seconds = time.perf_counter() - started
    phase('search_finished')
    verification_seconds = None
    if args.verify_final:
        phase('final_check_started')
        check_start = time.perf_counter()
        checker = mod.evaluate_scene_a
        if args.final_check_backend == 'counter':
            from q1_fast_evaluator import evaluate_scene_a as checker
        checked = checker(raw, plan, settings['bandwidth'], settings['capacity'],
                    waits['task_cross_core_wait_cycles'], waits['task_same_core_wait_cycles'])
        if checked != result:
            raise RuntimeError('Full final result differs from ' + args.final_check_backend + ' replay')
        verification_seconds = time.perf_counter() - check_start
        phase('final_check_finished')
    write_json(args.output / (args.graph.stem + '_multicore_res.json'), plan)
    write_json(args.output / 'search.json', stats)
    (args.output / 'evaluation.json.gz').write_bytes(gzip.compress(
        json.dumps(result, ensure_ascii=False, separators=(',', ':')).encode(), mtime=0))
    meta = {'algorithm': ADOPTED_POLICY, 'features': sorted(BASELINE_FEATURES),
            'seed': args.seed, 'budget': args.budget, 'cores': args.cores,
            'backend': args.backend, 'python': platform.python_version(),
            'input_sha256': sha(args.graph.read_bytes()), 'config_sha256': sha(args.config.read_bytes()),
            'solve_seconds': solve_seconds, 'verification_seconds': verification_seconds,
            'final_check_backend': args.final_check_backend if args.verify_final else None,
            'original_official_replayed': bool(args.verify_final and args.final_check_backend == 'official'),
            'total_seconds': time.perf_counter() - started,
            'makespan': result['makespan'], 'added_copy_bytes': result['data_movement_bytes']['added_copy_bytes'],
            'singlecore_makespan': stats['singlecore_makespan'],
            'speedup': stats['singlecore_makespan'] / result['makespan'],
            'source_sha256': {p.name: sha(p.read_bytes()) for p in sorted(Path(__file__).parent.glob('*.py'))}}
    write_json(args.output / 'run.json', meta)
    phase('complete')
    print(json.dumps({k: meta[k] for k in ('makespan', 'speedup', 'solve_seconds')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
