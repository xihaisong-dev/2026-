"""Evaluate a single frozen candidate pool; audit calls are not solver budget."""
import argparse
import gzip
import itertools
import json
from pathlib import Path
from q1_io import PROCESSED, official, verify, sha, write_json
from q1_ablation_report import collect
from q1_experimental import CostGraph
from q1_boundary_refine import pool
from q1_search_tools import replay
from q1_rank_metrics import metrics


def rank_report(rows, field):
    comparable = discordant = ties = 0
    for a, b in itertools.combinations(rows, 2):
        p, y = a[field]-b[field], a['official']-b['official']
        if not p or not y:
            ties += 1
        else:
            comparable += 1
            discordant += p*y < 0
    top = min(rows, key=lambda r: (r[field], r['label'])) if rows else None
    return {**metrics(rows, field), 'comparable': comparable, 'discordant': discordant, 'ties': ties,
            'top_label': top['label'] if top else None,
            'top_regret_cycles': top['official']-min(r['official'] for r in rows) if rows else None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runs', nargs='+', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    manifest = verify(); module = official()
    from evaluation_validation import read_evaluation_config
    from multicore_cut_evaluate_problem_1 import read_scene_a_config
    cfg = str(PROCESSED/'data/config.txt')
    settings, waits = read_evaluation_config(cfg), read_scene_a_config(cfg)
    summaries = {p: collect(p) for p in {r.parent for r in args.runs}}
    args.output.mkdir(parents=True, exist_ok=False)
    snapshot = args.output/'source_snapshot'; snapshot.mkdir()
    sources = {}
    for p in Path(__file__).parent.glob('*.py'):
        (snapshot/p.name).write_bytes(p.read_bytes()); sources[p.name] = sha(p.read_bytes())
    report = {'completed': False, 'reconstruction': 'incumbent-only observations; no original full search-state claim',
              'code_sha256': sources, 'source_zip_sha256': manifest['source_sha256'],
              'official_calls': 0, 'runs': []}
    for index, run in enumerate(args.runs):
        summary = summaries[run.parent]
        row = next(r for r in summary['runs'] if run.name == f"{r['case']}_{r['cores']}cores_seed{r['seed']}_{r['config']}")
        path = PROCESSED/'data'/(row['case']+'.json')
        if sha(path.read_bytes()) != summary['input_sha256'][path.name]:
            raise ValueError('Input mismatch')
        raw = json.loads(path.read_text(encoding='utf-8-sig'))
        plan = json.loads((run/'plan.json').read_text(encoding='utf-8'))
        incumbent = json.loads(gzip.decompress((run/'evaluation.json.gz').read_bytes()))
        g = CostGraph(raw, settings, waits, True); g.insertion = g.communication_rank = True
        g.observe(plan, incumbent)
        ranked, frozen = pool(g, plan, incumbent, row['cores'], True, True)
        # Compute every score BEFORE any candidate official result is available.
        pending = []
        for _, label, candidate in ranked:
            base, fluid = frozen.components(candidate)
            pending.append((label, candidate, base, fluid, frozen.score(candidate)))
        folder = args.output/f'{index:02d}_{row["case"]}_{row["cores"]}cores'; folder.mkdir()
        write_json(folder/'frozen_state.json', {'state_sha256': frozen.state,
                   'observations': sorted((list(k),v) for k,v in frozen.g.local_observations.items()),
                   'calibration': frozen.calibration, 'input_sha256': sha(path.read_bytes()),
                   'reference_artifacts': row['artifacts'], 'source_run': str(run)})
        rows = []
        for j, (label, candidate, base, fluid, calibrated) in enumerate(pending):
            result = module.evaluate_scene_a(raw, candidate, g.bandwidth, g.capacity, g.cross, g.same)
            report['official_calls'] += 1
            local = {int(s): p['local_makespan'] for s,p in result['step3_by_task'].items()}
            record = {'label': label, 'base': base, 'fluid': fluid, 'calibrated': calibrated,
                      'official': result['makespan'], 'oracle_local_replay': replay(g, candidate, local)}
            pp, ep = folder/f'{j:02d}_plan.json', folder/f'{j:02d}_evaluation.json.gz'
            write_json(pp, candidate)
            ep.write_bytes(gzip.compress(json.dumps(result,ensure_ascii=False).encode('utf-8'),mtime=0))
            record['artifacts'] = {pp.name: sha(pp.read_bytes()), ep.name: sha(ep.read_bytes())}
            rows.append(record)
            frozen.check()
        item = {'source': str(run), 'rows': rows, 'calibration': frozen.calibration,
                'state_sha256': frozen.state, 'stats': g.boundary_stats[-1],
                'rankings': {f: rank_report(rows,f) for f in ['base','fluid','calibrated','oracle_local_replay']}}
        report['runs'].append(item)
        write_json(args.output/'audit.json', report)
        print(row['case'],row['cores'],'candidates',len(rows),'alpha',frozen.alpha,flush=True)
    report['completed'] = True
    write_json(args.output/'audit.json', report)


if __name__ == '__main__':
    main()
