"""Reproduce shared_region for 1..5 cores, with bounded process parallelism."""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import csv
import gzip
import json
from pathlib import Path
import platform
from statistics import mean
import time
from q1_io import PROCESSED, official, verify, sha, write_json
from q1_submit import BASELINE_FEATURES


def run_case(job):
    case, output, backend, sources, inputs = job
    for name, digest in sources.items():
        if sha((Path(__file__).parent / name).read_bytes()) != digest:
            raise RuntimeError('Source changed during campaign: ' + name)
    for name in [f'data/{case}.json', 'data/config.txt']:
        if sha((PROCESSED / name).read_bytes()) != inputs[name]:
            raise RuntimeError('Input changed during campaign: ' + name)
    mod = official()
    from evaluation_validation import read_evaluation_config
    from singlecore_evaluate import build_singlecore_plan
    from q1_single_reference import reference
    from q1_experimental import solve_experimental
    evaluator = mod.evaluate_scene_a
    if backend == 'counter':
        from q1_fast_evaluator import evaluate_scene_a as evaluator
    raw = json.loads((PROCESSED / 'data' / (case + '.json')).read_text(encoding='utf-8-sig'))
    settings = read_evaluation_config(str(PROCESSED / 'data/config.txt'))
    waits = mod.read_scene_a_config(str(PROCESSED / 'data/config.txt'))
    started = time.perf_counter()
    plan = build_singlecore_plan(raw)
    single = evaluator(raw, plan, settings['bandwidth'], settings['capacity'],
                       waits['task_cross_core_wait_cycles'], waits['task_same_core_wait_cycles'])
    single_seconds = time.perf_counter() - started
    ref = reference(raw, settings, waits, single)
    rows = []
    for cores in range(1, 6):
        folder = Path(output) / case / f'{cores}cores'
        folder.mkdir(parents=True, exist_ok=False)
        if cores == 1:
            result, stats, seconds = single, None, single_seconds
        else:
            t = time.perf_counter()
            plan, result, stats = solve_experimental(raw, settings, waits, cores, 12, 0,
                BASELINE_FEATURES, single_reference=ref, evaluator_backend=backend)
            seconds = time.perf_counter() - t
            write_json(folder / 'search.json', stats)
        write_json(folder / f'{case}_multicore_res.json', plan)
        (folder / 'evaluation.json.gz').write_bytes(gzip.compress(json.dumps(result).encode(), mtime=0))
        row = dict(case=case, cores=cores, makespan=result['makespan'],
                   singlecore_makespan=single['makespan'], speedup=single['makespan'] / result['makespan'],
                   added_copy_bytes=result['data_movement_bytes']['added_copy_bytes'],
                   seconds=seconds, single_reference_seconds=single_seconds,
                   evaluated_opportunities=len(stats['evaluations']) if stats else 1)
        write_json(folder / 'row.json', row); rows.append(row)
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--workers', type=int, default=2)
    ap.add_argument('--backend', choices=['official', 'counter'], default='counter')
    ap.add_argument('--cases', nargs='+', default=[f'case_{i:03d}' for i in range(1, 101)])
    args = ap.parse_args()
    if args.workers < 1 or len(set(args.cases)) != len(args.cases):
        ap.error('Need positive workers and unique case names')
    manifest = verify()
    for case in args.cases:
        if f'data/{case}.json' not in manifest['files']:
            ap.error('Unknown case: ' + case)
    args.output.mkdir(parents=True, exist_ok=False)
    sources = {p.name: sha(p.read_bytes()) for p in Path(__file__).parent.glob('*.py')}
    rows = []
    write_json(args.output / 'protocol.json', dict(algorithm='shared_region', features=sorted(BASELINE_FEATURES),
        budget=12, seed=0, backend=args.backend, workers=args.workers, cases=args.cases,
        python=platform.python_version(), source_sha256=sources,
        input_manifest_sha256=sha((PROCESSED / 'manifest.json').read_bytes())))
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(run_case, (case, args.output, args.backend, sources, manifest['files'])): case for case in args.cases}
        for future in as_completed(futures):
            rows.extend(future.result())
            write_json(args.output / 'progress.json', dict(completed_cases=len(rows)//5, expected_cases=len(args.cases)))
            print(futures[future], 'complete', flush=True)
    rows.sort(key=lambda row: (row['case'], row['cores']))
    with (args.output / 'all_case_results.csv').open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    write_json(args.output / 'summary.json', dict(rows=rows,
        mean_speedup={str(n): mean(r['speedup'] for r in rows if r['cores'] == n) for n in range(1, 6)}))


if __name__ == '__main__':
    main()
