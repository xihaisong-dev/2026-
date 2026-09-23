"""Rescore saved frozen pools without regenerating candidates or new global calls."""
import argparse
import gzip
import json
from pathlib import Path
from q1_io import PROCESSED, official, verify, sha, write_json
from q1_experimental import CostGraph
from q1_local_rank import LocalRank
from q1_rank_metrics import metrics


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--phase', action='store_true')
    ap.add_argument('--audit', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    manifest = verify(); official()
    from evaluation_validation import read_evaluation_config
    from multicore_cut_evaluate_problem_1 import read_scene_a_config
    cfg = str(PROCESSED/'data/config.txt')
    settings, waits = read_evaluation_config(cfg), read_scene_a_config(cfg)
    source = json.loads((args.audit/'audit.json').read_text(encoding='utf-8'))
    assert source['completed'] and source['source_zip_sha256'] == manifest['source_sha256']
    args.output.mkdir(parents=True, exist_ok=False)
    snapshot = args.output/'source_snapshot'; snapshot.mkdir()
    for p in Path(__file__).parent.glob('*.py'):
        (snapshot/p.name).write_bytes(p.read_bytes())
    # Commit scores for ALL pools before opening any saved candidate outcomes.
    pending = []
    for i, item in enumerate(source['runs']):
        folder, = args.audit.glob(f'{i:02d}_*cores')
        state = json.loads((folder/'frozen_state.json').read_text(encoding='utf-8'))
        case = Path(item['source']).name[:8]
        path = PROCESSED/'data'/f'{case}.json'
        assert sha(path.read_bytes()) == state['input_sha256']
        raw = json.loads(path.read_text(encoding='utf-8-sig'))
        g = CostGraph(raw, settings, waits, True)
        ranker = LocalRank(raw, g, args.phase)
        rows = []
        for j, row in enumerate(item['rows']):
            pp = folder/f'{j:02d}_plan.json'
            assert sha(pp.read_bytes()) == row['artifacts'][pp.name]
            plan = json.loads(pp.read_text(encoding='utf-8'))
            score, duration, traffic = ranker.score(plan)
            from q1_search_tools import replay
            rows.append({'label': row['label'], 'local_exact': replay(g,plan,duration), 'phase': score,
                         'duration': duration, 'traffic': traffic,
                         'plan_sha256': sha(pp.read_bytes())})
        pending.append({'source': item['source'], 'rows': rows, 'preparation': ranker.stats()})
        print(case, len(rows), ranker.stats(), flush=True)
    write_json(args.output/'predictions.json', pending)
    for i, (item, output) in enumerate(zip(source['runs'], pending)):
        folder, = args.audit.glob(f'{i:02d}_*cores')
        for j, (old, row) in enumerate(zip(item['rows'],output['rows'])):
            ep = folder/f'{j:02d}_evaluation.json.gz'
            assert sha(ep.read_bytes()) == old['artifacts'][ep.name]
            result = json.loads(gzip.decompress(ep.read_bytes()))
            actual = {int(s): t['local_makespan'] for s,t in result['step3_by_task'].items()}
            assert actual == row.pop('duration'), 'Local preparation differs from official result'
            row.update(base=old['base'], official=result['makespan'])
        output['rankings'] = {f: metrics(output['rows'],f) for f in (['base','local_exact','phase'] if args.phase else ['base','local_exact'])}
    write_json(args.output/'report.json', {'completed': True, 'new_global_calls': 0,
               'source_audit_sha256': sha((args.audit/'audit.json').read_bytes()),
               'predictions_sha256': sha((args.output/'predictions.json').read_bytes()),
               'runs': pending})


if __name__ == '__main__':
    main()
