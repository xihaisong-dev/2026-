"""Read-only Q2 conformance audit plus lossless standard-name pilot export."""
import csv,gzip,json,subprocess,sys,time,os
from collections import defaultdict,Counter
from pathlib import Path
from q1_io import ROOT,PROCESSED,sha,write_json,verify
from q2_evaluator import load,check
from q2_physical import PhysicalScorer

OUT=ROOT/'审查/证据/20260924-A-q2-compliance-r04-v2'
R02=ROOT/'图表/runs/20260924-A-q2-main-r02'
R03=ROOT/'图表/runs/20260924-A-q2-controls-r03'


def read(p):return json.loads(p.read_text(encoding='utf-8'))


def main():
    assert not OUT.exists();OUT.mkdir(parents=True)
    settings,delay,prov=load();assert settings['bandwidth']==60 and settings['capacity']=={'L1':524288,'UB':131072} and delay==500
    from stub_multicore_cut_and_schedule import derive_multicore_plan
    from evaluation_validation import validate_task_order
    with (ROOT/'图表/runs/20260924-A-q1-delivery-r02/all_case_results.csv').open(encoding='utf-8-sig') as f:
        reference={r['case']:int(r['single_makespan']) for r in csv.DictReader(f)}
    input_edges=[]
    for i in range(1,101):
        raw=read(PROCESSED/f'data/case_{i:03}.json');ops={o['id'] for o in raw['ops']};tensors={t['id'] for t in raw['tensors']}
        bad=sum(not((e['source'] in ops and e['target'] in tensors) or (e['source'] in tensors and e['target'] in ops)) for e in raw['edges'])
        if bad:input_edges.append(dict(case=i,non_bipartite_edges=bad))
    audited=[];coverage=defaultdict(set)
    for run in [R02,R03]:
        for path in sorted(run.glob('*/*/*/*/row.json')):
            row=read(path);i=row['case'];k=row['cores'];folder=path.parent
            name='plan.json' if run==R03 else f'case_{i:03}_multicore_res.json'
            plan=read(folder/name);raw=read(PROCESSED/f'data/case_{i:03}.json')
            assert set(plan)=={'node_to_subgraph','core_schedules'} and len(plan['core_schedules'])==k
            view=derive_multicore_plan(raw,plan);validate_task_order(view)
            with gzip.open(folder/'evaluation.json.gz','rt',encoding='utf-8') as f:result=json.load(f)
            check(result,settings,delay)
            assert result['bandwidth_bytes_per_cycle']==60 and result['capacity_bytes']==settings['capacity']
            assert result['num_cores']==k and result['task_count']==k
            assert result['makespan']==row['makespan'] and result['data_movement_bytes']['added_copy_bytes']==row['bytes']
            assert row['reference']==reference[f'case_{i:03}'] and abs(row['speedup']-row['reference']/row['makespan'])<1e-12
            ends=[];original=Counter()
            required={o['id'] for o in raw['ops'] if o['op'] not in {'COPY_IN','COPY_OUT'}}
            for timeline in result['per_core_timeline']:
                pipes=defaultdict(list)
                for op in timeline['ops']:
                    assert op['duration']==op['end']-op['start'] and op['duration']>=0
                    ends.append(op['end']);pipes[op['pipe']].append((op['start'],op['end']))
                    if op['op_id'] in required:original[op['op_id']]+=1
                for intervals in pipes.values():
                    ordered=sorted(intervals);assert all(a[1]<=b[0] for a,b in zip(ordered,ordered[1:]))
            assert set(original)==required and all(n==1 for n in original.values())
            assert max(ends)==result['makespan']
            for transfer in result['cross_core_transfers']:
                assert transfer['copy_in_release']==transfer['copy_out_end']+500
                assert transfer['copy_in_start']>=transfer['copy_in_release']
            assert row['replay_equal'];coverage[i].add(k)
            audited.append(dict(path=path.relative_to(ROOT).as_posix(),plan_sha256=sha((folder/name).read_bytes()),evaluation_sha256=sha((folder/'evaluation.json.gz').read_bytes())))
    assert len(audited)==176
    # Real global residency, not just the official result's local Step3 peak.
    physical=[]
    for phase,i in [('development',12),('development',48),('development',50),('confirmation',18),('confirmation',33),('confirmation',67)]:
        folder=R03/phase/f'case_{i:03}/5/j_ordinary';raw=read(PROCESSED/f'data/case_{i:03}.json');plan=read(folder/'plan.json')
        with gzip.open(folder/'evaluation.json.gz','rt',encoding='utf-8') as f:result=json.load(f)
        t=time.perf_counter();profiles=PhysicalScorer(raw,settings,delay).actual_lifetimes(plan,result)
        physical.append(dict(case=i,cores=5,preparation_seconds=time.perf_counter()-t,
                             peaks={c:p['peak_bytes'] for c,p in profiles.items()}))
    exported=[]
    for phase in ['development','confirmation']:
        for path in sorted((R03/phase).glob('case_*/*/j_ordinary/plan.json')):
            row=read(path.parent/'row.json');i=row['case'];k=row['cores'];dest=OUT/f'standard_plans/{k}cores/case_{i:03}_multicore_res.json'
            dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(path.read_bytes())
            assert sha(dest.read_bytes())==sha(path.read_bytes())
            exported.append(dict(case=i,cores=k,path=dest.relative_to(ROOT).as_posix(),source=path.relative_to(ROOT).as_posix(),sha256=sha(dest.read_bytes())))
    cli=[]
    for phase,i,k in [('development',12,2),('development',48,5)]:
        plan=OUT/f'standard_plans/{k}cores/case_{i:03}_multicore_res.json';dest=OUT/f'official_cli/case_{i:03}_{k}';dest.mkdir(parents=True)
        cmd=[sys.executable,str(PROCESSED/'code/multicore_cut_evaluate_problem_2.py'),str(PROCESSED/f'data/case_{i:03}.json'),str(plan),'--config',str(PROCESSED/'data/config.txt'),'-o',str(dest/'result.json'),'--trace-output',str(dest/'trace.json'),'--log-output',str(dest/'log.txt')]
        p=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8',env=dict(os.environ,PYTHONIOENCODING='utf-8'));(dest/'stdout.txt').write_text(p.stdout+p.stderr,encoding='utf-8');assert p.returncode==0,p.stderr
        actual=read(dest/'result.json');actual.pop('input_graph');actual.pop('input_plan')
        with gzip.open(R03/phase/f'case_{i:03}/{k}/j_ordinary/evaluation.json.gz','rt',encoding='utf-8') as f:expected=json.load(f)
        assert actual==expected;cli.append(dict(case=i,cores=k,command=cmd,exit_code=p.returncode,full_result_equal=True))
    for run in [R02,R03]:
        c=read(run/'contract.json')
        for name,h in c['sources'].items():assert sha((ROOT/'程序'/name).read_bytes())==h
    verdict=dict(status='NOT_COMPLETE',algorithm_semantics='PASS_ON_AUDITED_EVIDENCE',full_requirement_compliance=False,
        research_optimization_eligible=True,reason='Hard modeling/solving constraints pass on audited evidence; full-data deliverables pending under the previously requested small-pilot-before-full100 workflow. This is not a complete-submission PASS.',
        audited_results=audited,case_coverage={str(i):sorted(ks) for i,ks in coverage.items()},unique_cases=len(coverage),unique_multicore_pairs=sum(map(len,coverage.values())),
        input_graphs_checked=100,non_bipartite_input_edges=input_edges,global_residency_samples=physical,standard_exports=exported,official_cli=cli,provenance=prov,
        missing=['one fixed adopted Q2 algorithm evaluated on all100 cases and cores2-5','full-data 1-5 core mean speedup line chart','full-data per-case Makespan/added-byte appendix','formal manuscript and reproducibility package acceptance'],
        caveats=['memory_peak_by_core is official local Step3 peak; actual global residency independently checked on six sampled final plans only','reference fixed-single counter backend is equivalent engineering implementation; sampled complete-output equivalence and historical fixed denominators checked, not a new all100 singlecore replay','r03 confirmation consists primarily of multiple small components; no independent dominant-component confirmation'])
    write_json(OUT/'audit.json',verdict)
    print(json.dumps({k:verdict[k] for k in ['status','algorithm_semantics','unique_cases','unique_multicore_pairs','non_bipartite_input_edges']}))


if __name__=='__main__':main()
