"""Polish existing solutions with an explicit additional global evaluation budget."""
import argparse
import gzip
import json
from pathlib import Path
import time
from q1_io import PROCESSED, verify, official, sha, write_json
from q1_ablation_report import collect
from q1_experimental import CostGraph
from q1_exact_placement import PartitionEvaluator, candidates


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--runs', type=Path, required=True)
    p.add_argument('--config', default='beam')
    p.add_argument('--extra-evaluations', type=int, default=8)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    if args.extra_evaluations < 1:
        p.error('extra-evaluations must be positive')
    verify()
    official()
    from evaluation_validation import read_evaluation_config
    from multicore_cut_evaluate_problem_1 import read_scene_a_config, evaluate_scene_a
    source = collect(args.runs)
    if args.config not in source['configs']:
        p.error('source does not contain requested config')
    config = str(PROCESSED/'data/config.txt')
    settings, waits = read_evaluation_config(config), read_scene_a_config(config)
    args.output.mkdir(parents=True, exist_ok=False)
    snapshot = args.output/'source_snapshot'
    snapshot.mkdir()
    hashes = {}
    for f in Path(__file__).parent.glob('*.py'):
        data = f.read_bytes()
        (snapshot/f.name).write_bytes(data)
        hashes[f.name] = sha(data)
    summary = {'completed': False, 'scope': 'additional_budget_postprocessing_not_equal_budget',
               'source_summary_sha256': sha((args.runs/'summary.json').read_bytes()),
               'source_code_sha256': hashes, 'extra_candidate_limit': args.extra_evaluations,
               'baseline_evaluations_per_run': source['evaluation_budget'], 'runs': []}
    write_json(args.output/'summary.json', summary)
    normalized = lambda r: json.loads(json.dumps(r))
    for row in source['runs']:
        if row['config'] != args.config:
            continue
        key = f"{row['case']}_{row['cores']}cores_seed{row['seed']}_{row['config']}"
        original = args.runs/key
        plan = json.loads((original/'plan.json').read_text(encoding='utf-8'))
        result = json.loads(gzip.decompress((original/'evaluation.json.gz').read_bytes()))
        data = (PROCESSED/'data'/(row['case']+'.json')).read_bytes()
        if sha(data) != source['input_sha256'][row['case']+'.json']:
            raise ValueError('Historical input changed')
        raw = json.loads(data.decode('utf-8-sig'))
        g = CostGraph(raw, settings, waits, True)
        g.observe(plan, result)
        t = time.perf_counter()
        pool = candidates(g, plan, result, args.extra_evaluations)
        engine = PartitionEvaluator(raw, g.bandwidth, g.capacity, g.cross, g.same)
        score = lambda r: (r['makespan'], r['data_movement_bytes']['added_copy_bytes'])
        best_plan, best_result = plan, result
        output = args.output/key
        output.mkdir()
        history = []
        for index, (label, trial, predicted) in enumerate(pool):
            start = time.perf_counter()
            evaluated = engine.evaluate(trial)
            elapsed = time.perf_counter()-start
            if score(evaluated) < score(best_result):
                best_plan, best_result = trial, evaluated
            history.append({'candidate': label, 'predicted': predicted,
                            'makespan': evaluated['makespan'],
                            'added_copy_bytes': score(evaluated)[1], 'seconds': elapsed})
            write_json(output/f'candidate_{index}_plan.json', trial)
        # Every delivered plan is independently re-evaluated by the untouched entry point.
        verified = evaluate_scene_a(raw, best_plan, g.bandwidth, g.capacity, g.cross, g.same)
        if normalized(verified) != normalized(best_result):
            raise ValueError('Exact replay disagrees with original evaluator')
        write_json(output/'plan.json', best_plan)
        write_json(output/'search.json', history)
        payload = gzip.compress(json.dumps(verified, ensure_ascii=False).encode('utf-8'), mtime=0)
        (output/'evaluation.json.gz').write_bytes(payload)
        summary['runs'].append({'case': row['case'], 'cores': row['cores'], 'seed': row['seed'],
                'before': result['makespan'], 'after': verified['makespan'],
                'before_added': score(result)[1], 'after_added': score(verified)[1],
                'extra_global_evaluations': len(pool), 'final_official_verifications': 1,
                'partition_cache_hits': engine.hits, 'partition_cache_misses': engine.misses,
                'seconds': time.perf_counter()-t,
                'artifacts': {f.name: sha(f.read_bytes()) for f in output.iterdir()}})
        write_json(args.output/'summary.json', summary)
        print(f"{key}: {result['makespan']} -> {verified['makespan']} ({len(pool)} extra candidates)", flush=True)
    summary['completed'] = True
    write_json(args.output/'summary.json', summary)


if __name__ == '__main__':
    main()
