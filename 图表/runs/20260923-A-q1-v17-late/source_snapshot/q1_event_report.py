"""Matched event/chain ablation audit, including explicit late-search ablation."""
import argparse
from collections import Counter
import gzip
import json
from pathlib import Path
from q1_io import write_json
from q1_ablation_report import collect,compare


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--runs',type=Path,nargs='+',required=True)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    rows=[];searches={};counts=Counter();chain=Counter();wall=[];seen=set();inputs={};zips=set()
    for folder in args.runs:
        summary=collect(folder);wall.append(summary.get('wall_seconds'));zips.add(summary['source_zip_sha256'])
        assert summary['evaluation_budget']==12
        for k,v in summary['input_sha256'].items():
            assert k not in inputs or inputs[k]==v
            inputs[k]=v
        for r in summary['runs']:
            key=(r['case'],r['cores'],r['seed'],r['config'])
            assert key not in seen;seen.add(key)
            run=folder/f'{key[0]}_{key[1]}cores_seed{key[2]}_{key[3]}'
            s=json.loads((run/'search.json').read_text(encoding='utf-8'));searches[key]=s
            ev={x['evaluation_id']:x for x in s['proposal_ledger'] if x['status']=='evaluated'}
            assert len(ev)==12 and len(s['protected_grain_ledger'])==4
            for x in s['proposal_ledger']:
                if x['status']=='duplicate':assert x['plan_sha256']==ev[x['evaluation_id']]['plan_sha256']
            counts.update(x['status'] for x in s['protected_grain_ledger'])
            for b in s['boundary_stats']:
                assert b['preparation']['global_evaluations']==0
                if b.get('event'):assert b['preparation']['event_passes']==3
            for b in s.get('chain_stats',[]):
                assert b['probes']<=12
                chain['enabled']+=b['enabled'];chain['probes']+=b['probes'];chain['valid']+=b['valid']
            result=json.loads(gzip.decompress((run/'evaluation.json.gz').read_bytes()))
            r['added_copy_bytes']=result['data_movement_bytes']['added_copy_bytes']
            r['prepare_seconds']=sum(b['preparation']['seconds'] for b in s['boundary_stats'])
            r['event_seconds']=sum(b['preparation'].get('event_seconds',0) for b in s['boundary_stats'])
            rows.append(r)
    assert len(zips)==1
    configs=sorted({r['config'] for r in rows})
    pairs=[('shared_region',c) for c in configs if c!='shared_region']
    pairs += [('shared_event','shared_event_chain')]
    if 'shared_event_late' in configs:pairs.append(('shared_event_chain','shared_event_late'))
    comparisons=[compare(rows,a,b) for a,b in pairs]
    totals={c:{f:sum(r[f] for r in rows if r['config']==c)
               for f in ['makespan','added_copy_bytes','seconds','prepare_seconds','event_seconds']} for c in configs}
    prefix_checked=0;late_indices=[]
    for key,s in searches.items():
        if key[-1]=='shared_region':continue
        idx=next((i for i,e in enumerate(s['evaluations']) if e['candidate'].startswith('region_')),None)
        if idx is None:continue
        if key[-1]=='shared_event_late':
            assert idx==11
            late_indices.append(idx)
        else:
            fields=lambda h:[(x['candidate'],x['makespan']) for x in h]
            assert fields(s['evaluations'][:idx])==fields(searches[key[:3]+('shared_region',)]['evaluations'][:idx])
            prefix_checked+=1
    per_core={str(k):{c:sum(r['makespan'] for r in rows if r['cores']==k and r['config']==c) for c in configs} for k in [2,3,4,5]}
    args.output.mkdir(parents=True,exist_ok=False)
    write_json(args.output/'comparison.json',{'completed':True,'totals':totals,'comparisons':comparisons,
               'per_core':per_core,'grain_status':dict(counts),'chain_probes':dict(chain),
               'prefix_checked':prefix_checked,'late_last_evaluations':len(late_indices),
               'official_calls':sum(r['official_calls'] for r in rows),'batch_wall_seconds':wall})


if __name__=='__main__':main()
