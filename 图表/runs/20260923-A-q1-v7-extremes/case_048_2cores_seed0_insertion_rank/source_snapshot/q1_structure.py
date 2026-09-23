"""Audit all graphs and freeze size-stratified structural representatives before solving."""
import argparse
from collections import Counter
import json
from pathlib import Path
from statistics import median
import subprocess
from q1_io import verify, official, PROCESSED, sha, write_json
from q1_solver import Graph
from q1_bounds import structural_bound


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    manifest = verify()
    official()
    from evaluation_validation import read_evaluation_config
    from multicore_cut_evaluate_problem_1 import read_scene_a_config
    config = str(PROCESSED/'data/config.txt')
    settings, waits = read_evaluation_config(config), read_scene_a_config(config)
    rows = []
    for path in sorted((PROCESSED/'data').glob('case_*.json')):
        raw = json.loads(path.read_text(encoding='utf-8-sig'))
        g = Graph(raw, settings, waits)
        b = structural_bound(g, 4)
        loads = b['noncopy_pipe_cycles']
        critical = b['compute_critical_path_cycles']
        work = sum(loads.values())
        rows.append({'case': path.stem, 'eligible_ops': len(g.ops), 'tensor_count': len(g.tensors),
                     'edges': sum(map(len, g.succ.values())), 'pipe_cycles': loads,
                     'dominant_pipe': max(loads, key=lambda x:(loads[x],x)),
                     'critical_path': critical, 'critical_fraction': critical/max(1,work),
                     'tensor_bytes_per_work_cycle': sum(t[0] for t in g.tensors)/max(1,work),
                     'fanout_max': max(map(len,g.succ.values()),default=0),
                     'input_sha256': sha(path.read_bytes()), 'bounds_2_to_5': {str(k):structural_bound(g,k)['lower_bound_cycles'] for k in range(2,6)}})
    rows.sort(key=lambda r:(r['eligible_ops'],r['case']))
    selected = []
    previous = {'case_001','case_002','case_034','case_078','case_093'}
    fields = ['eligible_ops','critical_fraction','tensor_bytes_per_work_cycle','fanout_max']
    for quartile in range(4):
        group = rows[len(rows)*quartile//4:len(rows)*(quartile+1)//4]
        center = {f:median(r[f] for r in group) for f in fields}
        spans = {f:max(r[f] for r in group)-min(r[f] for r in group) or 1 for f in fields}
        choices = [r for r in group if r['case'] not in previous]
        chosen = min(choices, key=lambda r:(sum(abs(r[f]-center[f])/spans[f] for f in fields),r['case']))
        selected.append({'size_quartile': quartile+1,'case':chosen['case'],
                         'eligible_ops':chosen['eligible_ops'], 'range':[group[0]['eligible_ops'],group[-1]['eligible_ops']]})
    args.output.mkdir(parents=True,exist_ok=False)
    write_json(args.output/'profile.json',{'source_zip_sha256':manifest['source_sha256'], 'cases':rows,
                'selection_rule':'one previously untested nearest normalized L1 median representative per size rank quartile; four structural dimensions; no scheduling scores used',
                'selection':selected,'known_tuning_cases':sorted(previous),
                'dominant_counts':dict(Counter(r['dominant_pipe'] for r in rows)),
                'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
                'code_sha256':{f.name:sha(f.read_bytes()) for f in Path(__file__).parent.glob('*.py')},
                'evaluation_protocol':{'cores':[2,3,4,5],'seeds':[0], 'configs':['insertion_rank','guarded_joint'],
                                       'candidate_budget':12,'cache':False,'per_run_timeout_seconds':90,
                                       'max_workers':2,'timeout_is_not_a_score':True}})
    print(json.dumps(selected,ensure_ascii=True))


if __name__ == '__main__':
    main()
