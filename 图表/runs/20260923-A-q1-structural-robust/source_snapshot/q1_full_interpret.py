"""Descriptive group analysis and witnessed nonmonotonicity; no result selection."""
import argparse
from collections import Counter,defaultdict
import csv
import json
from pathlib import Path
from statistics import mean
from q1_io import write_json,sha


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--analysis',type=Path,required=True);ap.add_argument('--census',type=Path,required=True)
    args=ap.parse_args();folder=args.analysis
    census={r['case']:r for r in json.loads(args.census.read_text(encoding='utf-8'))['cases']}
    profiles=json.loads((folder/'profiles.json').read_text(encoding='utf-8'))
    prof={(r['case'],r['cores'],r['config']):r for r in profiles}
    paired=json.loads((folder/'paired.json').read_text(encoding='utf-8'))
    with (folder/'all_case_results.csv').open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
    values={(r['case'],int(r['cores']),r['config']):r for r in rows}
    groups=defaultdict(list)
    for p in paired:
        c=census[p['case']];diag=prof[p['case'],p['cores'],'shared_region']
        groups['size_'+('small' if c['raw_ops']<2000 else 'medium' if c['raw_ops']<10000 else 'large')].append(p)
        groups['pipe_'+('concentrated' if c['dominant_pipe_share']>=.9 else 'mixed')].append(p)
        for tag in diag['tags']:groups['tag_'+tag].append(p)
    aggregated={}
    for key,ps in groups.items():
        aggregated[key]={'points':len(ps),'wins':sum(p['saved_cycles']>0 for p in ps),
            'ties':sum(p['saved_cycles']==0 for p in ps),'losses':sum(p['saved_cycles']<0 for p in ps),
            'sum_saved_cycles':sum(p['saved_cycles'] for p in ps),
            'mean_speedup_change':mean(p['speedup_change'] for p in ps),
            'mean_reduction_percent':mean(p['reduction_percent'] for p in ps)}
    monotonic=[]
    for case in sorted(census):
        for config in ['shared_region','shared_resource']:
            best=float(values[case,1,'fixed_single']['makespan']);bestk=1
            for k in [2,3,4,5]:
                t=float(values[case,k,config]['makespan'])
                if t>best:
                    monotonic.append({'case':case,'config':config,'cores':k,'makespan':t,
                        'witness_cores':bestk,'witness_makespan':best,'avoidable_cycles':t-best,
                        'reason':'The lower-core plan remains feasible when only empty cores are appended; unchanged shared bandwidth.'})
                if t<best:best=t;bestk=k
    base5=[r for r in rows if r['cores']=='5' and r['config']=='shared_region']
    worst=[]
    for r in sorted(base5,key=lambda r:float(r['speedup']))[:20]:
        p=prof[r['case'],5,'shared_region'];c=census[r['case']]
        worst.append({'case':r['case'],'speedup':float(r['speedup']),'makespan':float(r['makespan']),
            'raw_ops':c['raw_ops'],'dominant_pipe_share':c['dominant_pipe_share'],
            **{k:p[k] for k in ['tasks','used_cores','chain_wait_fraction','compute_path_fraction',
                 'ddr_busy_fraction','ddr_overlap_fraction','spill_added_copy_bytes','tags','pipe_occupancy']}})
    initial=[]
    for p in paired:
        a=values[p['case'],p['cores'],'shared_region']['initial_makespan']
        b=values[p['case'],p['cores'],'shared_resource']['initial_makespan']
        if a and b:initial.append({'case':p['case'],'cores':p['cores'],'before':float(a),'after':float(b)})
    out={'input_census_sha256':sha(args.census.read_bytes()),'code_sha256':sha(Path(__file__).read_bytes()),
        'groups_overlapping':aggregated,'lowest_five_core_speedup':worst,
        'core_nonmonotonicity':sorted(monotonic,key=lambda r:-r['avoidable_cycles']),
        'initial_comparison':{'pairs':len(initial),'wins':sum(r['after']<r['before'] for r in initial),
            'ties':sum(r['after']==r['before'] for r in initial),'losses':sum(r['after']>r['before'] for r in initial)},
        'worst_regressions':sorted(paired,key=lambda r:r['reduction_percent'])[:20],
        'largest_gains':sorted(paired,key=lambda r:-r['saved_cycles'])[:20],
        'warning':'Witness envelopes are diagnostic only, not substituted into measured speedup curves. Groups overlap.'}
    if (folder/'interpretation.json').exists():raise FileExistsError('Do not overwrite interpretation')
    write_json(folder/'interpretation.json',out)


if __name__=='__main__':main()
