"""Post-hoc fixed-partition diagnostic, separate from solver evaluation budgets."""
import argparse
import gzip
import json
from pathlib import Path
from q1_io import PROCESSED, official, verify, write_json, sha
from q1_ablation_report import collect
from q1_experimental import CostGraph
from q1_beam import schedule
from q1_search_tools import replay
from q1_solver import validate


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--runs', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    verify()
    official()
    from evaluation_validation import read_evaluation_config
    from multicore_cut_evaluate_problem_1 import read_scene_a_config, evaluate_scene_a
    config = str(PROCESSED / 'data/config.txt')
    settings, waits = read_evaluation_config(config), read_scene_a_config(config)
    summary = collect(args.runs)
    args.output.mkdir(parents=True, exist_ok=False)
    rows = []
    for row in summary['runs']:
        if row['config'] != 'insertion_rank':
            continue
        folder = args.runs / f"{row['case']}_{row['cores']}cores_seed{row['seed']}_insertion_rank"
        plan = json.loads((folder / 'plan.json').read_text(encoding='utf-8'))
        result = json.loads(gzip.decompress((folder / 'evaluation.json.gz').read_bytes()))
        raw = json.loads((PROCESSED / 'data' / (row['case']+'.json')).read_text(encoding='utf-8-sig'))
        g = CostGraph(raw, settings, waits, True)
        g.observe(plan, result)  # Only the already evaluated original partition.
        mapping = {int(u): s for u, s in plan['node_to_subgraph'].items()}
        before_proxy = replay(g, plan, g.costs(mapping)[0])
        candidate, proxy, info = schedule(g, mapping, row['cores'])
        if proxy >= before_proxy:
            candidate, proxy = plan, before_proxy
        validate(g, candidate)
        assert candidate['node_to_subgraph'] == plan['node_to_subgraph']
        changed = candidate != plan
        evaluated = evaluate_scene_a(raw, candidate, g.bandwidth, g.capacity, g.cross, g.same) if changed else result
        key = f"{row['case']}_{row['cores']}cores_seed{row['seed']}"
        write_json(args.output / (key+'_plan.json'), candidate)
        payload = gzip.compress(json.dumps(evaluated, ensure_ascii=False).encode('utf-8'), mtime=0)
        (args.output / (key+'_evaluation.json.gz')).write_bytes(payload)
        rows.append({'case': row['case'], 'cores': row['cores'], 'seed': row['seed'],
                     'before': result['makespan'], 'after': evaluated['makespan'],
                     'before_proxy': before_proxy, 'after_proxy': proxy,
                     'extra_official_calls': int(changed), 'beam': info,
                     'result_sha256': sha(payload), 'plan_sha256': sha((args.output/(key+'_plan.json')).read_bytes())})
    write_json(args.output/'probe.json', {'status': 'posthoc_fixed_partition_not_equal_budget_solver',
               'source_summary_sha256': sha((args.runs/'summary.json').read_bytes()),
               'source_sha256': {f.name: sha(f.read_bytes()) for f in Path(__file__).parent.glob('*.py')},
               'rows': rows, 'extra_official_calls': sum(r['extra_official_calls'] for r in rows)})


if __name__ == '__main__':
    main()
