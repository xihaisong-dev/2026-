"""Read saved full100 evidence; independently check actual selected residency."""
import argparse, concurrent.futures, gzip, json, time
from collections import Counter, defaultdict
from q1_io import ROOT, PROCESSED, sha, write_json
from q2_evaluator import load, check
from q2_physical import PhysicalScorer
from q2_full_campaign import OUT, read


def one(i):
    settings, delay, _ = load()
    from stub_multicore_cut_and_schedule import derive_multicore_plan
    from evaluation_validation import validate_task_order
    arm = read(OUT/'summary.json')['selected_global_algorithm']
    raw = read(PROCESSED/f'data/case_{i:03}.json')
    required = {o['id'] for o in raw['ops'] if o['op'] not in {'COPY_IN','COPY_OUT'}}
    answer = []
    for k in range(2,6):
        for a in ['legacy','routed']:
            folder = OUT/f'cases/case_{i:03}/{k}/{a}'
            p = folder/f'case_{i:03}_multicore_res.json'
            plan, row = read(p), read(folder/'row.json')
            assert set(plan) == {'node_to_subgraph','core_schedules'}
            assert len(plan['core_schedules']) == k
            validate_task_order(derive_multicore_plan(raw,plan))
            with gzip.open(folder/'evaluation.json.gz','rt',encoding='utf-8') as f:
                result = json.load(f)
            check(result,settings,delay)
            assert result['num_cores'] == result['task_count'] == k
            assert result['bandwidth_bytes_per_cycle'] == settings['bandwidth']
            assert result['capacity_bytes'] == settings['capacity']
            assert result['makespan'] == row['makespan']
            assert result['data_movement_bytes']['added_copy_bytes'] == row['bytes']
            assert abs(row['reference']/row['makespan']-row['speedup']) < 1e-12
            original, ends = Counter(), []
            for core in result['per_core_timeline']:
                pipes = defaultdict(list)
                for op in core['ops']:
                    assert op['duration'] == op['end']-op['start'] >= 0
                    ends.append(op['end'])
                    pipes[op['pipe']].append((op['start'],op['end']))
                    if op['op_id'] in required: original[op['op_id']] += 1
                for intervals in pipes.values():
                    intervals.sort()
                    assert all(x[1] <= y[0] for x,y in zip(intervals,intervals[1:]))
            assert set(original) == required and all(n == 1 for n in original.values())
            assert max(ends) == result['makespan']
            for transfer in result['cross_core_transfers']:
                assert transfer['copy_in_release'] == transfer['copy_out_end']+delay
                assert transfer['copy_in_start'] >= transfer['copy_in_release']
            record = dict(case=i,cores=k,arm=a,plan_sha256=sha(p.read_bytes()),
                          evaluation_sha256=sha((folder/'evaluation.json.gz').read_bytes()))
            if a == arm:
                t = time.perf_counter()
                profiles = PhysicalScorer(raw,settings,delay).actual_lifetimes(plan,result)
                record.update(actual_global_peaks={c:v['peak_bytes'] for c,v in profiles.items()},
                              prepare_seconds=time.perf_counter()-t)
            answer.append(record)
    return answer


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--workers',type=int,default=4);a=ap.parse_args()
    dest=OUT/'full_audit.json';assert not dest.exists()
    assert read(OUT/'summary.json')['audit']['final_replays'] == 800
    rows=[]
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers) as pool:
        for records in pool.map(one,range(1,101)):
            rows.extend(records);print('AUDITED',len(rows),flush=True)
    assert len(rows)==800 and sum('actual_global_peaks' in r for r in rows)==400
    write_json(dest,dict(status='PASS_ON_ALL_SAVED_RESULTS',results=800,
                        selected_global_residency_checks=400,records=rows,
                        limitations='No assertion of global optimality or formal manuscript acceptance.'))


if __name__=='__main__':main()
