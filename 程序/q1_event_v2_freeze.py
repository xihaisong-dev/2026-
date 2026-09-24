"""Audit cache-only revision and freeze a fresh, disjoint 400-job matrix."""
import argparse,gzip,json
from pathlib import Path
from q1_event_full_report import ROOT,read_rows,verify,load,key,write_json


def equivalent(a,b):
    assert (a/'plan.json').read_bytes()==(b/'plan.json').read_bytes()
    result=lambda p:json.loads(gzip.decompress((p/'evaluation.json.gz').read_bytes()))
    assert result(a)==result(b)
    signature=lambda p:[(r['candidate'],r['plan_sha256'],r['status'],r.get('evaluation_id')) for r in load(p/'search.json')['proposal_ledger']]
    assert signature(a)==signature(b)
    scores=lambda p:[{k:v for k,v in r.items() if k!='evaluation_seconds'} for r in load(p/'search.json')['evaluations']]
    assert scores(a)==scores(b)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--selection',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    a.output.mkdir(parents=True,exist_ok=False)
    base=ROOT/'图表/runs/20260924-A-q1-event-ranking'
    decision=load(a.selection/'selection.json')
    fallback=decision['variant']=='routes_gate_reuse'
    stage='gate_local_serial' if fallback else 'local_serial'
    probe_stage='gate_crossplatform_server' if fallback else 'crossplatform_server'
    control='routes_event_guarded' if fallback else 'routes_event_rank'
    trial=decision['variant']
    s,rows=read_rows(base/'v2-probes'/stage,verify())
    p,probe=read_rows(ROOT/'图表/runs/20260924-A-q1-event-ranking-v2/server/runs'/probe_stage,verify())
    assert s['code_sha256']==p['code_sha256'] and len(rows)==12 and len(probe)==1
    d={(r['case'],r['cores'],r['config']):r for r in rows};pairs=[]
    for c,k in sorted({key(r) for r in rows}):
        first=d[c,k,control];second=d[c,k,trial]
        equivalent(Path(first['source']),Path(second['source']))
        old=(ROOT/'图表/runs/20260924-A-q1-global-calibration/runs/development'/f'{c}_{k}cores_seed0_routes_event_guarded') if fallback else (base/'local/development_local'/f'{c}_{k}cores_seed0_routes_event_reuse')
        equivalent(Path(second['source']),old)
        pairs.append(dict(case=c,cores=k,uncached_seconds=first['solve_seconds'],cached_seconds=second['solve_seconds']))
    equivalent(Path(probe[0]['source']),Path(d['case_009',2,trial]['source']))
    decision['fallback_requires_equivalence_check']=False
    decision['fallback_equivalence_passed']=fallback
    result=dict(completed=True,pairs=6,all_plans_results_trajectories_equal=True,crossplatform_equal=True,code_sha256=s['code_sha256'],records=pairs,uncached_seconds=sum(x['uncached_seconds'] for x in pairs),cached_seconds=sum(x['cached_seconds'] for x in pairs),additional_runs=13,additional_full_search_calls=143)
    result['runtime_reduction_pct']=100*(1-result['cached_seconds']/result['uncached_seconds'])
    write_json(a.output/'equivalence.json',result)
    manifest=load(a.selection/'full_manifest.json');manifest['code_sha256']=s['code_sha256']
    manifest['reuse_validation_records']=[]
    cases=sorted({r['case'] for r in manifest['assignments']});assert len(cases)==100
    count=lambda c:sum(o['op'] not in ['COPY_IN','COPY_OUT'] for o in load(ROOT/'数据/processed/q1/data'/f'{c}.json')['ops'])
    ordered=sorted(cases,key=lambda c:(count(c),c));local=ordered[:30];server=list(reversed(ordered[30:]))
    manifest['hosts']={'local':{'pending_cases':local},'server':{'pending_cases':server}}
    manifest['assignments']=[dict(case=c,cores=k,host='local' if c in local else 'server') for c in cases for k in [2,3,4,5]]
    n=26 if fallback else 13
    manifest['diagnostic_budget']={'v1_validation_runs':129,'v1_search_calls':1419,'v2_probe_runs':n,'v2_probe_search_calls':11*n,'total_additional_search_calls':1419+11*n}
    manifest['revision']='V2 cache admission only; all 400 configurations recomputed with one source snapshot'
    write_json(a.output/'full_manifest.json',manifest)
    write_json(a.output/'selection.json',decision)
    print(json.dumps(dict(variant=manifest['variant'],local_cases=len(local),server_cases=len(server),runtime_reduction_pct=result['runtime_reduction_pct'])))


if __name__=='__main__':main()
