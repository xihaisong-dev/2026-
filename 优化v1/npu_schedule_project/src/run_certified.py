"""Certified faster search; every reported final result uses its official scene.

The original run_experiments.py remains the unchanged slow reproduction path.
Only candidate scores for verified equivalent, independent one-task-per-core
plans may use official B for problem 1. A winning such plan is reevaluated by
unaltered official A, and its makespan and complete traffic dictionary must
agree before the official A result is saved.
"""
from __future__ import annotations
import argparse
import concurrent.futures as cf
import hashlib
import json
import os
import platform
import sys
import time
import traceback
from pathlib import Path
from evaluate import ROOT, evaluate_plan, flatten_result, read_json, write_json, sha256_file
from run_experiments import baseline_job, aggregate, _plan_hash, check_manifest
from solver import generate_candidates
from certified_evaluate import evaluate_a_candidate, CERTIFICATE_VERSION


def _certificate_digest(metadata):
    if metadata.get('certificate_sha256'):return metadata['certificate_sha256']
    value=metadata.get('certificate',metadata)
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def selection_job(graph_path, output, cores, budget='standard'):
    graph_path,output=Path(graph_path),Path(output)
    case=graph_path.stem;n=int(cores);done=output/'records'/f'{case}_n{n}.json'
    if done.exists():return read_json(done)
    graph=read_json(graph_path);config=graph_path.parent/'config.txt'
    baseline=baseline_job(graph_path,output);base_time=baseline['makespan']
    base_result=read_json(output/'baselines'/(case+'.json.gz'))
    from singlecore_evaluate import build_singlecore_plan
    single_plan=build_singlecore_plan(graph);single_plan['core_schedules'] += [[] for _ in range(n-1)]
    allrows=[]
    for problem in (1,2):
        final_seconds=0.0;winner_certificate=None;winner_certificate_path=None
        if problem==1 and n==1:
            name,plan,result,solver_secs,eval_secs='official_singlecore',single_plan,base_result,0.0,baseline['evaluation_seconds']
            trials=[dict(case=case,problem=1,cores=1,method=name,status='ok',makespan=result['makespan'],evaluation_seconds=eval_secs,score_source='official_A_singlecore',certificate_passed=False)]
            winner_source='official_A_singlecore'
        else:
            ts=time.perf_counter()
            candidates=[('official_singlecore',single_plan)] if n==1 else generate_candidates(graph,n,problem=problem,budget=budget)
            solver_secs=time.perf_counter()-ts
            if not any(_plan_hash(p)==_plan_hash(single_plan) for _,p in candidates):candidates.append(('whole_graph',single_plan))
            best=None;trials=[];seen=set()
            for candidate_name,candidate_plan in candidates:
                h=_plan_hash(candidate_plan)
                if h in seen:continue
                seen.add(h);te=time.perf_counter();certificate_path=None;certificate_sha=None
                try:
                    if problem==1 and candidate_plan==single_plan:
                        candidate_result=base_result;source='reused_singlecore';metadata=dict(certificate_passed=False)
                    elif problem==1:
                        candidate_result,metadata=evaluate_a_candidate(graph,candidate_plan,config)
                        source='certified_official_B' if metadata.get('certificate_passed',False) else 'official_A'
                        scored_elapsed=time.perf_counter()-te
                        certificate_sha=_certificate_digest(metadata)
                        certificate_path=f'certificates/{case}_p1_n{n}_{h[:16]}.json'
                        write_json(output/certificate_path,dict(case=case,cores=n,method=candidate_name,plan_sha256=h,certificate_sha256=certificate_sha,metadata=metadata))
                    else:
                        candidate_result=evaluate_plan(graph,candidate_plan,2,config);source='official_B';metadata=dict(certificate_passed=False)
                    es=scored_elapsed if problem==1 and candidate_plan!=single_plan else time.perf_counter()-te
                    trial=flatten_result(candidate_result,case=case,problem=problem,method=candidate_name,baseline_makespan=base_time,evaluation_seconds=es,plan=candidate_plan)
                    trial.update(executed_task_count_derived=(len(set(candidate_plan['node_to_subgraph'].values())) if problem==1 else sum(bool(x) for x in candidate_plan['core_schedules'])),status='ok',plan_sha256=h,cores=n,reused_singlecore=source=='reused_singlecore',score_source=source,certificate_passed=metadata.get('certificate_passed',False),certificate_sha256=certificate_sha,certificate_path=certificate_path)
                    score=(candidate_result['makespan'],candidate_result['data_movement_bytes']['added_copy_bytes'],candidate_name)
                    if best is None or score<best[0]:best=(score,candidate_name,candidate_plan,candidate_result,es,source,certificate_sha,certificate_path)
                    trials.append(trial)
                except (ValueError, RuntimeError) as error:
                    trials.append(dict(case=case,problem=problem,cores=n,method=candidate_name,status='invalid',error=str(error),evaluation_seconds=time.perf_counter()-te,plan_sha256=h,score_source='evaluation_failed',certificate_sha256=certificate_sha,certificate_path=certificate_path))
                # New phase records every completed candidate for audit. These
                # checkpoints are never mistaken for a complete case record.
                write_json(output/'candidate_checkpoints'/f'{case}_p{problem}_n{n}.json',trials)
            if best is None:raise RuntimeError(f'No valid candidates for {case}, n={n}, problem={problem}')
            _,name,plan,result,eval_secs,winner_source,winner_certificate,winner_certificate_path=best
            if problem==1 and winner_source in ('certified_official_B','reused_singlecore'):
                score_result=result;te=time.perf_counter();result=evaluate_plan(graph,plan,1,config);final_seconds=time.perf_counter()-te;eval_secs=final_seconds
                if result['makespan']!=score_result['makespan'] or result['data_movement_bytes']!=score_result['data_movement_bytes']:
                    write_json(output/'certificate_failures'/f'{case}_n{n}.json',dict(method=name,score_source=winner_source,scored_makespan=score_result['makespan'],actual_makespan=result['makespan'],scored_movement=score_result['data_movement_bytes'],actual_movement=result['data_movement_bytes']))
                    raise AssertionError(f'Certified score and official A final verification differ for {case}, n={n}')
        if problem==1 and result.get('scene')!='A':raise AssertionError('Final problem-1 artifact must be a genuine official scene-A result')
        stem=f'{case}_p{problem}_n{n}'
        write_json(output/'plans'/(stem+'.json'),plan)
        write_json(output/'official_results'/(stem+'.json.gz'),result)
        write_json(output/'candidates'/(stem+'.json'),trials)
        search_secs=sum(x['evaluation_seconds'] for x in trials)
        row=flatten_result(result,case=case,problem=problem,method=name,baseline_makespan=base_time,evaluation_seconds=eval_secs,solver_seconds=solver_secs,plan=plan)
        row.update(executed_task_count_derived=(len(set(plan['node_to_subgraph'].values())) if problem==1 else sum(bool(x) for x in plan['core_schedules'])),candidate_count=len(trials),invalid_candidate_count=sum(x['status']!='ok' for x in trials),search_evaluation_seconds=search_secs,final_verification_seconds=final_seconds,total_evaluation_seconds=search_secs+final_seconds,official_result_path='official_results/'+stem+'.json.gz',plan_path='plans/'+stem+'.json',cache_speedup_vs_same_plan=None,search_engine=CERTIFICATE_VERSION,score_source=winner_source,final_result_source='official_A' if problem==1 else 'official_B',certificate_sha256=winner_certificate,certificate_path=winner_certificate_path)
        allrows.append(row)
        if problem==2:
            te=time.perf_counter();cached=evaluate_plan(graph,plan,3,config);ecs=time.perf_counter()-te
            stem3=f'{case}_p3_n{n}';write_json(output/'plans'/(stem3+'.json'),plan);write_json(output/'official_results'/(stem3+'.json.gz'),cached)
            cr=flatten_result(cached,case=case,problem=3,method=name,baseline_makespan=base_time,evaluation_seconds=ecs,solver_seconds=0.0,plan=plan)
            cr.update(executed_task_count_derived=sum(bool(x) for x in plan['core_schedules']),candidate_count=1,invalid_candidate_count=0,search_evaluation_seconds=ecs,final_verification_seconds=0.0,total_evaluation_seconds=ecs,official_result_path='official_results/'+stem3+'.json.gz',plan_path='plans/'+stem3+'.json',cache_speedup_vs_same_plan=result['makespan']/cached['makespan'] if cached['makespan'] else None,search_engine=CERTIFICATE_VERSION,score_source='official_C',final_result_source='official_C',certificate_sha256=None,certificate_path=None)
            allrows.append(cr)
    write_json(done,allrows);return allrows


def engine_manifest(output):
    source_names=['run_certified.py','certified_evaluate.py','check_certified_engine.py']
    paths=[ROOT/'src'/s for s in source_names]
    manifest=dict(engine=CERTIFICATE_VERSION,frozen_run_manifest_sha256=sha256_file(Path(output)/'run_manifest.json'),source_sha256={p.name:sha256_file(p) for p in paths},final_results='Every final P1 result is unmodified official A; P2 official B; P3 official C; certified B scores are candidate search only.')
    path=Path(output)/'certified_engine_manifest.json'
    if path.exists() and read_json(path)!=manifest:raise RuntimeError('Certified engine source changed. Use a separate output directory rather than mix engine versions.')
    write_json(path,manifest)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--data',type=Path,default=ROOT/'data')
    ap.add_argument('--output',type=Path,default=ROOT/'results')
    ap.add_argument('--workers',type=int,default=min(8,os.cpu_count() or 1))
    ap.add_argument('--cores',nargs='+',type=int,default=[1,2,3,4,5])
    ap.add_argument('--cases',nargs='*')
    ap.add_argument('--budget',default='standard')
    ap.add_argument('--stop-file',type=Path,help='Stop submitting new jobs when this file exists; allow in-flight jobs to finish')
    args=ap.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    check_manifest(args.output,args.budget,args.data);engine_manifest(args.output)
    write_json(args.output/'certified_execution_environment.json',dict(python=sys.version,platform=platform.platform(),logical_cpus=os.cpu_count(),workers=args.workers,budget=args.budget))
    cases=sorted(args.data.glob('case_*.json'),key=lambda p:p.stat().st_size,reverse=True)
    if args.cases:cases=[p for p in cases if p.stem in args.cases]
    missing=[p for p in cases if not (args.output/'baselines'/(p.stem+'.meta.json')).exists()]
    if missing:
        with cf.ProcessPoolExecutor(max_workers=args.workers) as pool:
            list(pool.map(baseline_job,map(str,missing),[str(args.output)]*len(missing)))
    jobs=[(p,n) for p in cases for n in args.cores if not (args.output/'records'/f'{p.stem}_n{n}.json').exists()]
    active={};errors=[];total=len(jobs);completed=0;started=time.perf_counter();last_log=0
    with cf.ProcessPoolExecutor(max_workers=args.workers) as pool:
        while jobs or active:
            stopping=args.stop_file and args.stop_file.exists()
            while jobs and len(active)<args.workers and not stopping:
                p,n=jobs.pop(0)
                active[pool.submit(selection_job,str(p),str(args.output),n,args.budget)]=f'{p.stem}/n{n}'
            if not active:break
            finished,_=cf.wait(active,timeout=5,return_when=cf.FIRST_COMPLETED)
            for future in finished:
                label=active.pop(future);completed+=1
                try:future.result();print(f'[{completed}/{total}] {label}: OK, elapsed {time.perf_counter()-started:.1f}s',flush=True)
                except Exception as error:
                    errors.append(dict(job=label,error=str(error),traceback=traceback.format_exc()));print(f'[{completed}/{total}] {label}: ERROR {error}',flush=True)
                write_json(args.output/'certified_run_errors.json',errors)
                if completed%5==0:aggregate(args.output)
            if time.perf_counter()-last_log>=30:
                state=dict(engine='certified',completed=completed,total=total,active=list(active.values()),remaining=len(jobs),elapsed_seconds=time.perf_counter()-started,draining=bool(stopping))
                write_json(args.output/'certified_progress.json',state);print(state,flush=True);last_log=time.perf_counter()
    aggregate(args.output)
    if errors:raise SystemExit(1)
    print(f'Finished certified phase in {time.perf_counter()-started:.1f}s; remaining queued jobs={len(jobs)}',flush=True)

if __name__=='__main__':main()
