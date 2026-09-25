"""Independent checks on saved official results and exact input-file integrity."""
from __future__ import annotations
import argparse
import csv
import math
import hashlib
import json
from collections import Counter, defaultdict, deque
from pathlib import Path
from evaluate import ROOT, read_json, write_json, sha256_file


def validate_plan_independent(graph,plan,scene='A'):
    eligible={o['id'] for o in graph['ops'] if o['op'] not in ('COPY_IN','COPY_OUT')}
    mapping={int(k):v for k,v in plan['node_to_subgraph'].items()}
    assert set(mapping)==eligible, 'Eligible operation coverage is not exact'
    placed=[s for row in plan['core_schedules'] for s in row]
    assert len(placed)==len(set(placed)), 'Repeated subgraph in core schedules'
    assert set(placed)==set(mapping.values()), 'Subgraph schedule coverage mismatch'
    sg_core={sg:c for c,row in enumerate(plan['core_schedules']) for sg in row}
    op_core={o:sg_core[sg] for o,sg in mapping.items()}
    producers=defaultdict(list);consumers=defaultdict(list)
    for e in graph['edges']:
        if e['source'] in eligible:producers[e['target']].append(e['source'])
        if e['target'] in eligible:consumers[e['source']].append(e['target'])
    pairs={(a,b) for tid,ps in producers.items() for a in ps for b in consumers.get(tid,[]) if a!=b}
    arcs={(mapping[a],mapping[b]) for a,b in pairs if mapping[a]!=mapping[b]}
    # Scene A tasks are serial. In B only operation FIFO/order is binding;
    # treating whole subgraphs as serial would reject legal pipe overlap.
    if scene=='A': arcs.update((a,b) for row in plan['core_schedules'] for a,b in zip(row,row[1:]))
    adjacency=defaultdict(set);indegree=dict.fromkeys(placed,0)
    for a,b in arcs:
        if b not in adjacency[a]:adjacency[a].add(b);indegree[b]+=1
    q=deque(a for a,d in indegree.items() if d==0);count=0
    while q:
        a=q.popleft();count+=1
        for b in adjacency[a]:
            indegree[b]-=1
            if indegree[b]==0:q.append(b)
    assert count==len(indegree), 'Partition and per-core order induce a cycle'
    return eligible,op_core,pairs


def validate_result(graph,plan,result):
    eligible,op_core,pairs=validate_plan_independent(graph,plan,result['scene'])
    assert result['num_cores']==len(plan['core_schedules']), 'Core count mismatch'
    computation={};ends=[];checks=0
    for core in result['per_core_timeline']:
        by_pipe=defaultdict(list)
        for op in core['ops']:
            assert op['end']>=op['start']>=0, 'Invalid operation interval'
            assert op['duration']==op['end']-op['start'], 'Invalid duration'
            ends.append(op['end']);by_pipe[op['pipe']].append(op)
            if op['op_id'] in eligible:
                assert op['op_id'] not in computation,'Duplicate original compute op'
                assert op_core[op['op_id']]==core['core_id'],'Wrong compute core'
                computation[op['op_id']]=op
            checks+=1
        for pipe,ops in by_pipe.items():
            previous=0
            for op in sorted(ops,key=lambda x:(x['start'],x['end'])):
                if op['duration']>0:
                    assert op['start']>=previous,f'Pipe overlap on core {core["core_id"]}, {pipe}'
                    previous=op['end']
    assert set(computation)==eligible,'Missing original compute operations'
    for a,b in pairs:
        assert computation[a]['end']<=computation[b]['start'],f'Original dependency violated {a}->{b}'
    assert result['makespan']==max(ends,default=0),'Makespan not maximum operation finish'
    for v in result['memory_peak_by_core'].values():
        for loc in ('L1','UB'):
            assert 0<=v[loc]<=result['capacity_bytes'][loc],f'{loc} capacity violated'
    for link in result.get('cross_core_transfers',[]):
        assert link['copy_in_start']>=link['copy_out_end']+result['cross_core_copy_delay_cycles'],'Cross-core sync delay violated'
        assert link['copy_in_end']>=link['copy_in_start'],'Invalid transfer interval'
    m=result['data_movement_bytes']
    assert m['scheduled_copy_bytes']-m['original_graph_copy_bytes']==m['added_copy_bytes'],'Traffic total identity'
    assert m['partition_added_copy_bytes']+m['spill_added_copy_bytes']==m['added_copy_bytes'],'Traffic decomposition identity'
    c=result.get('cache_stats')
    if c:
        denominator=c['hit_bytes']+c['miss_bytes']
        assert abs(c['hit_rate']-(c['hit_bytes']/denominator if denominator else 0))<1e-12,'Cache byte hit-rate mismatch'
        assert c['hits']==c['copy_in_hits'] and c['accesses']==c['copy_in_hits']+c['copy_in_misses'],'Cache count mismatch'
        assert c['hit_bytes']<=m['scheduled_copy_bytes'],'Cache hits exceed traffic'
        for e in result['cache_events']:
            if e['event']=='insert':assert e['used_bytes']<=result['cache_capacity_bytes'],'L2 capacity violation'
    return dict(operations_checked=checks,original_computations_checked=len(eligible),original_dependencies_checked=len(pairs))


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--results',type=Path,default=ROOT/'results')
    ap.add_argument('--allow-partial',action='store_true')
    args=ap.parse_args();errors=[];totals=Counter();validated=0
    manifest=read_json(ROOT/'official_checksums.json')
    for rel,expected in manifest.items():
        actual=sha256_file(ROOT/rel)
        if actual!=expected:errors.append(dict(file=rel,error='SHA256 differs from supplied original'))
    run_manifest_path=args.results/'run_manifest.json'
    if run_manifest_path.exists():
        for name,expected in read_json(run_manifest_path)['source_sha256'].items():
            if sha256_file(ROOT/'src'/name)!=expected:
                errors.append(dict(file='src/'+name,error='Algorithm/evaluator wrapper changed after the recorded run started'))
    certified_manifest_path=args.results/'certified_engine_manifest.json'
    if certified_manifest_path.exists():
        cm=read_json(certified_manifest_path)
        for name,expected in cm['source_sha256'].items():
            if sha256_file(ROOT/'src'/name)!=expected:errors.append(dict(file='src/'+name,error='Certified engine source changed after recording'))
        if cm['frozen_run_manifest_sha256']!=sha256_file(args.results/'run_manifest.json'):errors.append(dict(error='Certified engine references a different original source manifest'))
    correction_path=args.results/'metadata_corrections.json'
    metadata_official_hashes_checked=0
    if correction_path.exists():
        correction=read_json(correction_path)
        for rel,expected in correction['official_result_hashes_unchanged'].items():
            if sha256_file(args.results/rel)!=expected:errors.append(dict(file=rel,error='Official JSON changed after metadata-only correction'))
            metadata_official_hashes_checked+=1
        for revision in read_json(args.results/'source_revisions.json'):
            old=args.results/revision['computed_source_archive']/Path(revision['source_file']).name
            if sha256_file(old)!=revision['source_before_sha256']:errors.append(dict(error='Archived computed source hash mismatch'))
            if sha256_file(ROOT/revision['source_file'])!=revision['source_after_sha256']:errors.append(dict(error='Current corrected source hash mismatch'))
    records=[]
    for f in sorted((args.results/'records').glob('*.json')):records.extend(read_json(f))
    graphs={}
    for row in records:
        stem=f'{row["case"]}_p{row["problem"]}_n{row["cores"]}'
        try:
            if row['case'] not in graphs: graphs[row['case']]=read_json(ROOT/'data'/(row['case']+'.json'))
            graph=graphs[row['case']]
            plan=read_json(args.results/'plans'/(stem+'.json'))
            result=read_json(args.results/'official_results'/(stem+'.json.gz'))
            totals.update(validate_result(graph,plan,result));validated+=1
            assert row['makespan']==result['makespan'],'CSV/record result mismatch'
            if 'official_task_count' in row:assert row['official_task_count']==result.get('task_count'),'Official task-count metadata mismatch'
            if 'executed_task_count_derived' in row:
                expected_tasks=len(set(plan['node_to_subgraph'].values())) if row['problem']==1 else sum(bool(order) for order in plan['core_schedules'])
                assert row['executed_task_count_derived']==expected_tasks,'Derived task-count metadata mismatch'
            assert abs(row['speedup']-row['baseline_makespan']/result['makespan'])<1e-12,'Speedup mismatch'
            if row.get('score_source')=='certified_official_B':
                assert row['problem']==1 and result['scene']=='A' and row['final_result_source']=='official_A','A proxy was reported as a final A result'
                assert row['final_verification_seconds']>0,'Certified winner was not genuinely reevaluated'
                cert=read_json(args.results/row['certificate_path']);meta=cert['metadata']
                evidence=dict(version=meta['certificate_version'],passed=meta['certificate_passed'],reason=meta['reason'],per_core=meta['per_core'],traffic=meta.get('certified_data_movement_bytes'))
                digest=hashlib.sha256(json.dumps(evidence,sort_keys=True,separators=(',',':')).encode()).hexdigest()
                assert digest==meta['certificate_sha256']==row['certificate_sha256']==cert['certificate_sha256'],'Certificate hash mismatch'
                assert meta['certificate_passed'] and all(x.get('equivalent',x.get('exact_equal',False)) for x in meta['per_core']),'Failed equivalence certificate'
                candidates=read_json(args.results/'candidates'/(stem+'.json'))
                winner=next(x for x in candidates if x['method']==row['method'])
                assert winner['makespan']==result['makespan'],'Certified-score/final makespan mismatch'
                for key,value in result['data_movement_bytes'].items():assert winner[key]==value,'Certified-score/final traffic mismatch'
            if 'total_evaluation_seconds' in row:
                assert abs(row['total_evaluation_seconds']-row['search_evaluation_seconds']-row['final_verification_seconds'])<1e-7,'Evaluation timing identity mismatch'
            if row['problem']==3:
                plan_b=read_json(args.results/'plans'/(f'{row["case"]}_p2_n{row["cores"]}.json'))
                assert plan==plan_b,'Problem 3 is not paired with exactly the problem-2 plan'
        except Exception as e:errors.append(dict(result=stem,error=str(e)))
    expected={(f.stem,p,n) for f in (ROOT/'data').glob('case_*.json') for p in (1,2,3) for n in (1,2,3,4,5)}
    observed={(r['case'],r['problem'],r['cores']) for r in records}
    missing=sorted(expected-observed)
    unexpected=sorted(observed-expected)
    if unexpected:errors.append(dict(error='Unexpected case/problem/core combinations',items=unexpected))
    if len(records)!=len(observed):errors.append(dict(error='Duplicate case/problem/core records'))
    if not args.allow_partial and missing: errors.append(dict(error='Incomplete official case/configuration coverage',missing_count=len(missing)))
    report=dict(status='PASS' if not errors else 'FAIL',validated_results=validated,expected_results=len(expected),missing_results=missing,checks=dict(totals),input_files_checked=len(manifest),metadata_official_hashes_checked=metadata_official_hashes_checked,errors=errors)
    write_json(args.results/'validation_report.json',report)
    print(f'{report["status"]}: {validated}/{len(expected)} official results, {len(errors)} errors; checks={dict(totals)}')
    if errors:raise SystemExit(1)

if __name__=='__main__':main()
