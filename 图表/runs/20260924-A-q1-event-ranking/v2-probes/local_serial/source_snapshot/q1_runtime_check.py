"""Compare full accelerated results with frozen official evidence, without caches."""
import argparse
import gzip
import json
import platform
import time
from pathlib import Path
from q1_io import PROCESSED, official, verify, write_json, sha


def read_result(path):
    return json.loads(gzip.decompress(path.read_bytes()))


def canonical(value):
    return json.loads(json.dumps(value))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--cases', nargs='+', default=[f'case_{i:03d}' for i in range(1, 101)])
    ap.add_argument('--paired-single', action='store_true')
    ap.add_argument('--solve', action='store_true')
    ap.add_argument('--cores', nargs='+', type=int, default=[2, 3, 4, 5])
    ap.add_argument('--slow-only', action='store_true', help='Re-solve only archived searches exceeding 600 seconds')
    args = ap.parse_args()
    verify(); mod = official()
    from evaluation_validation import read_evaluation_config
    from singlecore_evaluate import build_singlecore_plan
    from q1_fast_evaluator import evaluate_scene_a, BACKEND_ID
    from q1_single_reference import reference
    from q1_experimental import solve_experimental
    from q1_submit import BASELINE_FEATURES
    settings = read_evaluation_config(str(PROCESSED / 'data/config.txt'))
    waits = mod.read_scene_a_config(str(PROCESSED / 'data/config.txt'))
    kwargs = dict(bandwidth=settings['bandwidth'], capacity=settings['capacity'],
                  cross_core_wait=waits['task_cross_core_wait_cycles'], same_core_wait=waits['task_same_core_wait_cycles'])
    args.output.mkdir(parents=True, exist_ok=False)
    rows = []
    for case in args.cases:
        raw = json.loads((PROCESSED / 'data' / (case + '.json')).read_text(encoding='utf-8-sig'))
        whole = build_singlecore_plan(raw)
        t = time.perf_counter(); single = evaluate_scene_a(raw, whole, **kwargs); dt = time.perf_counter() - t
        single_seconds = dt
        old = read_result(args.run / case / 'single/evaluation.json.gz')
        old.pop('execution_mode', None); old.pop('input_plan', None)
        assert canonical(single) == old, (case, 'single result mismatch')
        row = dict(case=case, cores=1, seconds=dt, full_result_equal=True)
        if args.paired_single:
            t = time.perf_counter(); original = mod.evaluate_scene_a(raw, whole, **kwargs)
            row['original_seconds'] = time.perf_counter() - t
            assert original == single
            row['runtime_speedup'] = row['original_seconds'] / dt
        rows.append(row); print(row, flush=True)
        ref = reference(raw, settings, waits, single)
        for n in args.cores:
            folder = args.run / case / f'{n}cores_shared_region'
            if args.slow_only and json.loads((folder / 'row.json').read_text(encoding='utf-8'))['seconds'] <= 600:
                continue
            plan = json.loads((folder / 'plan.json').read_text(encoding='utf-8'))
            expected = read_result(folder / 'evaluation.json.gz')
            t = time.perf_counter(); result = evaluate_scene_a(raw, plan, **kwargs); dt = time.perf_counter() - t
            assert canonical(result) == expected, (case, n, 'result mismatch')
            row = dict(case=case, cores=n, seconds=dt, full_result_equal=True)
            if args.solve:
                t = time.perf_counter()
                p, r, s = solve_experimental(raw, settings, waits, n, 12, 0, BASELINE_FEATURES,
                                            single_reference=ref, evaluator_backend='counter')
                row['search_seconds'] = time.perf_counter() - t
                row['search_plus_single_seconds'] = row['search_seconds'] + single_seconds
                old_search = json.loads((folder / 'search.json').read_text(encoding='utf-8'))
                def trajectory(stats):
                    return [(x['candidate'], x['makespan'], x['added_copy_bytes']) for x in stats['evaluations']]
                assert p == plan and canonical(r) == expected, (case, n, 'search result mismatch')
                assert trajectory(s) == trajectory(old_search), (case, n, 'trajectory mismatch')
                assert [x['plan_sha256'] for x in s['proposal_ledger']] == [x['plan_sha256'] for x in old_search['proposal_ledger']], (case, n, 'proposal mismatch')
                row.update(search_equal=True, evaluated_opportunities=len(s['evaluations']))
                write_json(args.output / f'{case}_{n}_search.json', s)
            rows.append(row); print(row, flush=True)
        write_json(args.output / 'checks.json', dict(backend=BACKEND_ID, python=platform.python_version(),
                   source_sha256={p.name: sha(p.read_bytes()) for p in Path(__file__).parent.glob('*.py')},
                   frozen_summary_sha256=sha((args.run / 'summary.json').read_bytes()), rows=rows))


if __name__ == '__main__':
    main()
