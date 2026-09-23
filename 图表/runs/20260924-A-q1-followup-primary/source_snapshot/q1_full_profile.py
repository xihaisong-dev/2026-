"""Audit full coverage and produce per-case speedups and descriptive bottlenecks."""
import argparse
from collections import Counter,defaultdict
import csv
import gzip
import json
from pathlib import Path
from statistics import mean,median
from q1_io import PROCESSED,official,sha,write_json,verify


def ddr_intervals(result):
    ids={(x['issued']['task_id'],x['issued']['op_id']) for x in result['ddr_contention_log']}
    events=defaultdict(int)
    for core in result['per_core_timeline']:
        for op in core['ops']:
            if (op['task_id'],op['op_id']) in ids:
                events[op['start']]+=1;events[op['end']]-=1
    busy=overlap=active=peak=0;previous=0
    for t,delta in sorted(events.items()):
        busy+=(t-previous)*(active>0);overlap+=(t-previous)*(active>1)
        active+=delta;peak=max(peak,active);previous=t
    return busy,overlap,peak


def profile(g,plan,result):
    from q1_bounds import structural_bound
    from q1_critical_chain import critical_chain
    k=len(plan['core_schedules']);t=result['makespan']
    bound=structural_bound(g,k)
    chain,_,info=critical_chain(g,plan,result)
    if info['profile_path']!=t:raise ValueError('Task release profile mismatch')
    owner={s:c for c,seq in enumerate(plan['core_schedules']) for s in seq}
    pipe=defaultdict(int);percore=[]
    for c in result['per_core_timeline']:
        percore.append(sum(x['duration'] for x in c['tasks']))
        for x in c['ops']:pipe[x['pipe']]+=x['duration']
    busy,overlap,peak=ddr_intervals(result)
    movement=result['data_movement_bytes']
    tasks=[x for c in result['per_core_timeline'] for x in c['tasks']]
    local={int(s):x['local_makespan'] for s,x in result['step3_by_task'].items()}
    stretch=sum(x['duration']-local[x['task_id']] for x in tasks)
    cp=bound['compute_critical_path_cycles'];lb=bound['lower_bound_cycles']
    row={'tasks':len(tasks),'used_cores':sum(bool(s) for s in plan['core_schedules']),
         'critical_chain_tasks':len(chain),'chain_core_switches':sum(owner[a]!=owner[b] for a,b in zip(chain,chain[1:])),
         'chain_release_wait_cycles':info['wait_cycles'],'chain_wait_fraction':info['wait_fraction'],
         'compute_critical_path':cp,'structural_lower_bound':lb,'lower_bound_gap_fraction':(t-lb)/t,
         'compute_path_fraction':cp/t,'task_occupied_fraction':sum(percore)/(k*t),
         'ddr_busy_fraction':busy/t,'ddr_overlap_fraction':overlap/t,'max_active_ddr':peak,
         'task_duration_stretch_sum':stretch,'spill_added_copy_bytes':movement['spill_added_copy_bytes'],
         'partition_added_copy_bytes':movement['partition_added_copy_bytes'],
         'scheduled_copy_bytes':movement['scheduled_copy_bytes'],
         'pipe_occupancy':{p:v/(k*t) for p,v in pipe.items()}}
    tags=[]
    if cp/t>=.7:tags.append('compute_dependency')
    if info['wait_fraction']>=.2:tags.append('task_release_wait')
    if busy/t>=.65:tags.append('ddr_busy')
    if overlap/t>=.25:tags.append('ddr_overlap')
    if movement['spill_added_copy_bytes']>0:tags.append('spill_present')
    if row['used_cores']<k and cp/t<.5:tags.append('mapping_review')
    row['tags']=tags or ['mixed']
    return row


def read_result(folder):
    return json.loads(gzip.decompress((folder/'evaluation.json.gz').read_bytes()))


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args();manifest=verify();official()
    from evaluation_validation import read_evaluation_config
    from multicore_cut_evaluate_problem_1 import read_scene_a_config
    from q1_solver import Graph,validate
    settings=read_evaluation_config(str(PROCESSED/'data/config.txt'))
    waits=read_scene_a_config(str(PROCESSED/'data/config.txt'))
    report=json.loads((args.run/'summary.json').read_text(encoding='utf-8'))
    if not report['completed']:raise ValueError('Campaign incomplete')
    expected={Path(r['case']).stem for r in manifest['cases']}
    assert {r['case'] for r in report['cases']}==expected and len(report['cases'])==100
    assert report['config_sha256']==sha((PROCESSED/'data/config.txt').read_bytes())
    for name,h in report['code_sha256'].items():assert sha((args.run/'source_snapshot'/name).read_bytes())==h
    rows=[];single_rows=[];profiles=[];grain=Counter();newcalls=0
    for item in sorted(report['cases'],key=lambda r:r['case']):
        case=item['case'];rawpath=PROCESSED/'data'/f'{case}.json'
        assert sha(rawpath.read_bytes())==report['input_sha256'][case+'.json']
        raw=json.loads(rawpath.read_text(encoding='utf-8-sig'));g=Graph(raw,settings,waits)
        single=item['single'];folder=args.run/case/'single'
        assert sha((folder/'evaluation.json.gz').read_bytes())==single['evaluation_sha256']
        assert read_result(folder)['makespan']==single['makespan'];single_rows.append(single);newcalls+=single['official_calls']
        assert len(item['runs'])==8
        assert {(r['cores'],r['config']) for r in item['runs']}=={(k,c) for k in [2,3,4,5] for c in report['configs']}
        for saved in item['runs']:
            row=dict(saved);folder=args.run/case/f"{row['cores']}cores_{row['config']}"
            for name,h in row['artifacts'].items():assert sha((folder/name).read_bytes())==h
            plan=json.loads((folder/'plan.json').read_text(encoding='utf-8'))
            stats=json.loads((folder/'search.json').read_text(encoding='utf-8'));result=read_result(folder)
            validate(g,plan)
            assert stats['singlecore_makespan']==single['makespan']
            assert stats['official_calls']+stats['cache_hits']==len(stats['evaluations'])<=report['evaluation_budget']
            assert row['makespan']==result['makespan']==min(e['makespan'] for e in stats['evaluations'])
            assert row['speedup']==single['makespan']/row['makespan']
            row['initial_makespan']=next((e['makespan'] for e in stats['evaluations'] if e['candidate'] in ['greedy','resource_initial']),None)
            row['initial_tasks']=len(stats.get('resource_init_stats',{}).get('blocks',[])) or None
            row['best_candidate']=min(stats['evaluations'],key=lambda e:(e['makespan'],e['added_copy_bytes']))['candidate']
            row['noncopy_ops']=len(g.ops)
            profiles.append({'case':case,'cores':row['cores'],'config':row['config'],**profile(g,plan,result)})
            for e in stats['protected_grain_ledger']:grain[e['status']]+=1
            assert stats['protected_grain_attempts']==[.5,1.,2.,.25]
            newcalls+=row['official_calls'];rows.append(row)
        print('PROFILE',case,flush=True)
    summaries={}
    for config in report['configs']:
        summaries[config]={}
        for k in [1,2,3,4,5]:
            subset=single_rows if k==1 else [r for r in rows if r['config']==config and r['cores']==k]
            assert len(subset)==100
            summaries[config][str(k)]={'cases':100,'mean_speedup':mean(r['speedup'] for r in subset),
                'sum_makespan':sum(r['makespan'] for r in subset),'sum_added_copy_bytes':sum(r['added_copy_bytes'] for r in subset),
                'median_solve_seconds':median(r['seconds'] for r in subset),'max_solve_seconds':max(r['seconds'] for r in subset),
                'over_300_seconds':sum(r['seconds']>300 for r in subset),'over_600_seconds':sum(r['seconds']>600 for r in subset)}
    bykey={(r['case'],r['cores'],r['config']):r for r in rows};paired=[]
    for case in sorted(expected):
        for k in [2,3,4,5]:
            a=bykey[case,k,'shared_region'];b=bykey[case,k,'shared_resource']
            paired.append({'case':case,'cores':k,'before':a['makespan'],'after':b['makespan'],
                'saved_cycles':a['makespan']-b['makespan'],'reduction_percent':100*(a['makespan']-b['makespan'])/a['makespan'],
                'added_bytes_change':b['added_copy_bytes']-a['added_copy_bytes'],
                'speedup_change':b['speedup']-a['speedup']})
    args.output.mkdir(parents=True,exist_ok=False)
    write_json(args.output/'profiles.json',profiles);write_json(args.output/'paired.json',paired)
    fields=['case','cores','config','makespan','singlecore_makespan','speedup','added_copy_bytes','seconds','official_calls','initial_makespan','best_candidate','noncopy_ops']
    with (args.output/'all_case_results.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(single_rows+rows)
    summary={'completed':True,'source_summary_sha256':sha((args.run/'summary.json').read_bytes()),
        'profile_code_sha256':sha(Path(__file__).read_bytes()),'solver_runs':800,'single_baselines':100,
        'max_fixed_baseline_compute_seconds':max(r.get('reference_compute_seconds',r['seconds']) for r in single_rows),
        'fixed_baselines_over_600_seconds':sum(r.get('reference_compute_seconds',r['seconds'])>600 for r in single_rows),
        'official_calls':newcalls,'calls_this_attempt':sum(r.get('calls_this_attempt',r['official_calls']) for r in rows)+sum(r['official_calls'] for r in single_rows),'grain_ledger':dict(grain),'by_core':summaries,
        'wins':sum(p['saved_cycles']>0 for p in paired),'ties':sum(p['saved_cycles']==0 for p in paired),
        'losses':sum(p['saved_cycles']<0 for p in paired),'sum_saved_cycles':sum(p['saved_cycles'] for p in paired),
        'limitations':['descriptive all-case study, not an independent holdout','fixed official count, not same wall time',
          'tags overlap and do not add to makespan','structural bound gap is not attainable improvement']}
    write_json(args.output/'summary.json',summary)


if __name__=='__main__':main()
