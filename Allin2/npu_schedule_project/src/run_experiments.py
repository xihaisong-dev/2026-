"""Run deterministic candidate selection and the unchanged official evaluators.

A full run records 100 * 3 * 5 selected results. Complete operation timelines are
stored as lossless .json.gz files; plans and per-candidate audit logs stay JSON.
"""
from __future__ import annotations
import argparse
import concurrent.futures as cf
import csv
import json
import os
import platform
import sys
import time
import traceback
from pathlib import Path
from evaluate import ROOT, evaluate_plan, evaluate_singlecore, flatten_result, read_json, write_json, sha256_file


def baseline_job(graph_path, output):
    graph_path, output = Path(graph_path), Path(output)
    dest=output/'baselines'/(graph_path.stem+'.json.gz')
    meta=output/'baselines'/(graph_path.stem+'.meta.json')
    if dest.exists() and meta.exists(): return read_json(meta)
    meta.parent.mkdir(parents=True,exist_ok=True)
    lock=meta.with_suffix('.lock')
    while True:
        try:
            fd=os.open(str(lock),os.O_CREAT|os.O_EXCL|os.O_WRONLY)
            os.write(fd,str(os.getpid()).encode());os.close(fd);break
        except FileExistsError:
            if dest.exists() and meta.exists(): return read_json(meta)
            time.sleep(.2)
    try:
        if dest.exists() and meta.exists(): return read_json(meta)
        graph=read_json(graph_path); t=time.perf_counter(); result=evaluate_singlecore(graph,graph_path.parent/'config.txt')
        elapsed=time.perf_counter()-t
        result['input_graph']=graph_path.name; write_json(dest,result)
        row=flatten_result(result,case=graph_path.stem,problem=0,method='official_singlecore',baseline_makespan=result['makespan'],evaluation_seconds=elapsed)
        write_json(meta,row); return row
    finally:
        lock.unlink(missing_ok=True)


def _plan_hash(plan):
    # Stable hash of the exact official submission JSON.
    import hashlib
    data=json.dumps(plan,sort_keys=True,separators=(',',':')).encode()
    return hashlib.sha256(data).hexdigest()


_EVAL_STATE = {}


def _init_eval_worker(graph_path, problem, config_path):
    """Load one graph per worker. Windows spawn cannot share the parent graph."""
    _EVAL_STATE['graph'] = read_json(graph_path)
    _EVAL_STATE['problem'] = int(problem)
    _EVAL_STATE['config'] = config_path


def _eval_task(candidate_name, candidate_plan, plan_hash):
    started = time.perf_counter()
    try:
        result = evaluate_plan(
            _EVAL_STATE['graph'], candidate_plan, _EVAL_STATE['problem'], _EVAL_STATE['config'])
        return dict(ok=True, method=candidate_name, plan_sha256=plan_hash, result=result,
                    evaluation_seconds=time.perf_counter() - started)
    except Exception as error:
        return dict(ok=False, method=candidate_name, plan_sha256=plan_hash, error=str(error),
                    evaluation_seconds=time.perf_counter() - started)


def _wall_origin():
    """perf_counter timestamp for this case, set in the parent before hashing inputs."""
    raw = os.environ.get('ALLIN2_CASE_START')
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _evaluate_parallel(graph_path, pending, problem, n, case, base_time, base_result, single_plan, config, workers):
    """Score candidates on separate processes. Trial order stays the generation order."""
    best = None
    trials = [None] * len(pending)
    jobs = []
    for index, (candidate_name, candidate_plan, plan_hash) in enumerate(pending):
        if candidate_plan == single_plan and problem == 1:
            trial = flatten_result(base_result, case=case, problem=problem, method=candidate_name,
                                   baseline_makespan=base_time, evaluation_seconds=0.0, plan=candidate_plan)
            trial.update(status='ok', plan_sha256=plan_hash, reused_singlecore=True, cores=n)
            score = (base_result['makespan'], base_result['data_movement_bytes']['added_copy_bytes'], candidate_name)
            if best is None or score < best[0]:
                best = (score, candidate_name, candidate_plan, base_result, 0.0)
            trials[index] = trial
        else:
            jobs.append(index)
    if jobs:
        pool_size = max(1, min(int(workers), len(jobs)))
        print(f'{case} n={n} evaluating {len(jobs)} candidates on {pool_size} workers', flush=True)
        with cf.ProcessPoolExecutor(max_workers=pool_size, initializer=_init_eval_worker,
                                     initargs=(str(graph_path), int(problem), str(config))) as pool:
            futures = {}
            for index in jobs:
                candidate_name, candidate_plan, plan_hash = pending[index]
                futures[pool.submit(_eval_task, candidate_name, candidate_plan, plan_hash)] = index
            for future in cf.as_completed(futures):
                index = futures[future]
                payload = future.result()
                candidate_name, candidate_plan, plan_hash = pending[index]
                if payload['ok']:
                    result = payload['result']
                    elapsed = payload['evaluation_seconds']
                    trial = flatten_result(result, case=case, problem=problem, method=candidate_name,
                                           baseline_makespan=base_time, evaluation_seconds=elapsed, plan=candidate_plan)
                    trial.update(status='ok', plan_sha256=plan_hash, reused_singlecore=False, cores=n)
                    score = (result['makespan'], result['data_movement_bytes']['added_copy_bytes'], candidate_name)
                    if best is None or score < best[0]:
                        best = (score, candidate_name, candidate_plan, result, elapsed)
                    trials[index] = trial
                else:
                    trials[index] = dict(case=case, problem=problem, cores=n, method=candidate_name, status='invalid',
                                         error=payload['error'], evaluation_seconds=payload['evaluation_seconds'],
                                         plan_sha256=plan_hash)
    return best, [trial for trial in trials if trial is not None]


def selection_job(graph_path, output, cores, budget, problems=(1, 2), eval_workers=1):
    from solver import generate_candidates
    graph_path, output=Path(graph_path),Path(output)
    case=graph_path.stem; n=int(cores)
    done=output/'records'/f'{case}_n{n}.json'
    if done.exists(): return read_json(done)
    t_wall0=_wall_origin()
    if t_wall0 is None:
        t_wall0=time.perf_counter()
    graph=read_json(graph_path); config=graph_path.parent/'config.txt'
    baseline=baseline_job(graph_path,output); base_time=baseline['makespan']
    base_result=read_json(output/'baselines'/(case+'.json.gz'))
    from singlecore_evaluate import build_singlecore_plan
    single_plan=build_singlecore_plan(graph)
    single_plan['core_schedules'] += [[] for _ in range(n-1)]
    allrows=[]
    # Problem 3 is not selected on its own. It reuses the problem-2 winner below.
    for problem in tuple(int(p) for p in problems):
        # At n=1 problem 1 is explicitly the official singlecore benchmark.
        if problem==1 and n==1:
            name, plan, result, solver_secs, eval_secs='official_singlecore',single_plan,base_result,0.0,baseline['evaluation_seconds']
            trials=[dict(method=name,status='ok',makespan=result['makespan'],evaluation_seconds=eval_secs)]
        else:
            ts=time.perf_counter()
            candidates=[('official_singlecore',single_plan)] if n==1 else generate_candidates(graph,n,problem=problem,budget=budget)
            solver_secs=time.perf_counter()-ts
            # The uncut graph is a feasible candidate at every core count.
            if not any(_plan_hash(p)==_plan_hash(single_plan) for _,p in candidates):
                candidates.append(('whole_graph',single_plan))
            best=None; trials=[]; seen=set(); pending=[]
            for candidate_name,candidate_plan in candidates:
                h=_plan_hash(candidate_plan)
                if h in seen: continue
                seen.add(h)
                pending.append((candidate_name, candidate_plan, h))
            if int(eval_workers) > 1:
                best, trials = _evaluate_parallel(
                    graph_path, pending, problem, n, case, base_time, base_result, single_plan, config, eval_workers)
            else:
              for candidate_name, candidate_plan, h in pending:
                te=time.perf_counter()
                try:
                    if candidate_plan==single_plan and problem==1:
                        # Score only: identical single active core. If it wins, run
                        # the official n-core evaluator below; do not synthesize traces.
                        candidate_result=base_result
                        reused=True
                    else:
                        candidate_result=evaluate_plan(graph,candidate_plan,problem,config);reused=False
                    es=time.perf_counter()-te
                    trial=flatten_result(candidate_result,case=case,problem=problem,method=candidate_name,baseline_makespan=base_time,evaluation_seconds=es,plan=candidate_plan)
                    trial.update(status='ok',plan_sha256=h,reused_singlecore=reused,cores=n)
                    score=(candidate_result['makespan'],candidate_result['data_movement_bytes']['added_copy_bytes'],candidate_name)
                    if best is None or score<best[0]: best=(score,candidate_name,candidate_plan,candidate_result,es)
                    trials.append(trial)
                except Exception as error:
                    trials.append(dict(case=case,problem=problem,cores=n,method=candidate_name,status='invalid',error=str(error),evaluation_seconds=time.perf_counter()-te,plan_sha256=h))
            if best is None: raise RuntimeError(f'No valid candidates for {case}, n={n}, problem={problem}')
            _,name,plan,result,eval_secs=best
            if problem==1 and plan==single_plan:
                te=time.perf_counter(); result=evaluate_plan(graph,plan,1,config); eval_secs=time.perf_counter()-te
            # Refine only while the constructive search is still inside the
            # 600-second soft target. A case already past that target keeps
            # its selected plan and is recorded as slow, without another
            # hill-climb of official evaluations.
            if problem==1 and n==5:
                search_so_far=sum(x.get('evaluation_seconds',0) for x in trials)
                # Entry stays on the sum of official evaluations, so a case that
                # skipped the hill-climb before still skips it. The deadline is
                # wall-clock from the start of this case, including the read.
                remain = 600 - (time.perf_counter() - t_wall0)
                if search_so_far < 600 and remain > 15:
                    from solver import GraphModel
                    from ls_p1n5 import budgets_for, local_search
                    model=GraphModel(graph)
                    spec=budgets_for(len(model.ids))
                    if spec is not None:
                        it, tt, bud = spec
                        t_ls=time.perf_counter()
                        try:
                            found=local_search(graph, model, plan, config, n, it, tt, bud, deadline=t_wall0 + 600)
                        except Exception:
                            found=None
                        ls_secs=time.perf_counter()-t_ls
                        if found is not None:
                            mk, added, ls_plan = found
                            seed_score=(result['makespan'], result['data_movement_bytes']['added_copy_bytes'])
                            if (mk, added) < seed_score:
                                te=time.perf_counter()
                                confirmed=evaluate_plan(graph, ls_plan, 1, config)
                                confirm_secs=time.perf_counter()-te
                                ls_secs += confirm_secs
                                confirmed_score=(confirmed['makespan'], confirmed['data_movement_bytes']['added_copy_bytes'])
                                if confirmed_score < seed_score:
                                    result=confirmed
                                    plan=ls_plan
                                    name='ls_'+name
                                    eval_secs=confirm_secs
                        trials.append(dict(case=case,problem=problem,cores=n,method='ls_refine',status='ok',evaluation_seconds=ls_secs,makespan=result['makespan']))
        stem=f'{case}_p{problem}_n{n}'
        write_json(output/'plans'/(stem+'.json'),plan)
        write_json(output/'official_results'/(stem+'.json.gz'),result)
        write_json(output/'candidates'/(stem+'.json'),trials)
        row=flatten_result(result,case=case,problem=problem,method=name,baseline_makespan=base_time,evaluation_seconds=eval_secs,solver_seconds=solver_secs,plan=plan)
        cpu_sum=sum(x['evaluation_seconds'] for x in trials)
        wall=time.perf_counter()-t_wall0
        # Parallel runs report worker wall-clock in the 600-second field.
        # search_cpu_seconds keeps the old sum of official evaluations.
        reported = wall if int(eval_workers) > 1 else cpu_sum
        row.update(candidate_count=len(trials),invalid_candidate_count=sum(x['status']!='ok' for x in trials),
                   search_evaluation_seconds=reported, search_cpu_seconds=cpu_sum, search_wall_seconds=wall,
                   eval_workers=int(eval_workers),
                   official_result_path='official_results/'+stem+'.json.gz',plan_path='plans/'+stem+'.json',
                   cache_speedup_vs_same_plan=None)
        allrows.append(row)
        if problem==2:
            te=time.perf_counter();cached=evaluate_plan(graph,plan,3,config);ecs=time.perf_counter()-te
            stem3=f'{case}_p3_n{n}'
            write_json(output/'plans'/(stem3+'.json'),plan)
            write_json(output/'official_results'/(stem3+'.json.gz'),cached)
            cr=flatten_result(cached,case=case,problem=3,method=name,baseline_makespan=base_time,evaluation_seconds=ecs,solver_seconds=0.0,plan=plan)
            cr.update(candidate_count=1,invalid_candidate_count=0,search_evaluation_seconds=ecs,
                      official_result_path='official_results/'+stem3+'.json.gz',plan_path='plans/'+stem3+'.json',
                      cache_speedup_vs_same_plan=result['makespan']/cached['makespan'] if cached['makespan'] else None)
            allrows.append(cr)
    write_json(done,allrows)
    return allrows


def aggregate(output):
    output=Path(output); rows=[]
    for f in sorted((output/'records').glob('*.json')): rows.extend(read_json(f))
    rows.sort(key=lambda r:(r['case'],r['cores'],r['problem']))
    if rows:
        columns=list(dict.fromkeys(k for r in rows for k in r))
        with (output/'results.csv').open('w',newline='',encoding='utf-8-sig') as f:
            w=csv.DictWriter(f,fieldnames=columns);w.writeheader();w.writerows(rows)
        summary=[]
        import statistics
        for problem in (1,2,3):
            for n in range(1,6):
                group=[r for r in rows if r['problem']==problem and r['cores']==n]
                if not group: continue
                s=dict(problem=problem,cores=n,cases=len(group))
                for key in ('speedup','makespan','added_copy_bytes','partition_added_copy_bytes','spill_added_copy_bytes','cache_hit_rate','cache_speedup_vs_same_plan','solver_seconds','search_evaluation_seconds'):
                    vals=[r[key] for r in group if r.get(key) is not None]
                    if vals: s['mean_'+key]=statistics.mean(vals)
                s['median_speedup']=statistics.median(r['speedup'] for r in group)
                s['invalid_candidates']=sum(r['invalid_candidate_count'] for r in group)
                s['cache_hit_rate_pooled']=sum(r['cache_hit_bytes'] for r in group)/max(1,sum(r['cache_hit_bytes']+r['cache_miss_bytes'] for r in group))
                summary.append(s)
        write_json(output/'summary.json',summary)
    trials=[]
    for f in sorted((output/'candidates').glob('*.json')):
        for row in read_json(f):
            if 'case' not in row:
                parts=f.stem.split('_');row.update(case='_'.join(parts[:2]),problem=int(parts[2][1:]),cores=int(parts[3][1:]))
            trials.append(row)
    if trials:
        columns=list(dict.fromkeys(k for r in trials for k in r))
        with (output/'candidates.csv').open('w',newline='',encoding='utf-8-sig') as f:
            w=csv.DictWriter(f,fieldnames=columns);w.writeheader();w.writerows(trials)
    return len(rows)


def check_manifest(output,budget,data,problems):
    """Reject mixing saved results produced by different source/config versions."""
    paths=[ROOT/'src'/'solver.py', ROOT/'src'/'stitch_candidates.py', ROOT/'src'/'extra_candidates.py', ROOT/'src'/'ls_p1n5.py', ROOT/'src'/'evaluate.py', ROOT/'src'/'run_experiments.py']
    manifest=dict(schema=1,budget=budget,problems=list(problems),source_sha256={p.name:sha256_file(p) for p in paths},
                  official_inputs=read_json(ROOT/'official_checksums.json'),
                  data_sha256={p.name:sha256_file(p) for p in sorted(Path(data).glob('*')) if p.is_file()})
    path=Path(output)/'run_manifest.json'
    if path.exists() and read_json(path)!=manifest:
        raise RuntimeError('Saved run manifest differs from current source/config/data. Use a new --output folder to avoid mixing experiments.')
    write_json(path,manifest)


def run_selected_dispatch(pool,cases,args):
    pending=[(p,n) for p in cases for n in args.cores if not (args.output/'records'/f'{p.stem}_n{n}.json').exists()]
    active={};errors=[];completed=0;started=time.perf_counter();last_log=0
    total=len(pending)
    while pending or active:
        ready_cases={p.stem for p in cases if (args.output/'baselines'/(p.stem+'.meta.json')).exists()}
        limit=args.workers if len(ready_cases)==len(cases) else args.initial_workers
        while len(active)<limit:
            idx=next((i for i,(p,n) in enumerate(pending) if p.stem in ready_cases),None)
            if idx is None:break
            p,n=pending.pop(idx)
            future=pool.submit(selection_job,str(p),str(args.output),n,args.budget,tuple(args.problems),1)
            active[future]=f'{p.stem}/n{n}'
        if active:
            done,_=cf.wait(active,timeout=5,return_when=cf.FIRST_COMPLETED)
            for future in done:
                label=active.pop(future);completed+=1
                try:
                    future.result();print(f'[{completed}/{total}] {label}: OK, elapsed {time.perf_counter()-started:.1f}s',flush=True)
                except Exception as error:
                    errors.append(dict(job=label,error=str(error),traceback=traceback.format_exc()))
                    print(f'[{completed}/{total}] {label}: ERROR {error}',flush=True)
                write_json(args.output/'run_errors.json',errors)
                if completed%5==0 or completed==total:aggregate(args.output)
        else:
            time.sleep(1)
        now=time.perf_counter()
        if now-last_log>=30:
            state=dict(completed=completed,total=total,baselines_ready=len(ready_cases),baselines_expected=len(cases),active=list(active.values()),remaining=len(pending),elapsed_seconds=now-started)
            write_json(args.output/'progress.json',state)
            print(f'Progress: {completed}/{total} jobs, baselines {len(ready_cases)}/{len(cases)}, active {len(active)}, elapsed {now-started:.1f}s',flush=True);last_log=now
    return errors


def _run_cases_inline(cases, args):
    """One case at a time in this process. Each case has its own evaluation pool."""
    pending=[(p,n) for p in cases for n in args.cores if not (args.output/'records'/f'{p.stem}_n{n}.json').exists()]
    errors=[]; completed=0; started=time.perf_counter(); total=len(pending)
    for index, (p, n) in enumerate(pending):
        # Start each search window after the shared single-core baseline work.
        os.environ['ALLIN2_CASE_START'] = str(time.perf_counter())
        label=f'{p.stem}/n{n}'
        try:
            selection_job(str(p), str(args.output), n, args.budget, tuple(args.problems), args.eval_workers)
            completed += 1
            print(f'[{completed}/{total}] {label}: OK, elapsed {time.perf_counter()-started:.1f}s', flush=True)
        except Exception as error:
            completed += 1
            errors.append(dict(job=label, error=str(error), traceback=traceback.format_exc()))
            print(f'[{completed}/{total}] {label}: ERROR {error}', flush=True)
        write_json(args.output/'run_errors.json', errors)
        if completed % 5 == 0 or completed == total:
            aggregate(args.output)
    return errors


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--data',type=Path,default=ROOT/'data')
    ap.add_argument('--output',type=Path,default=ROOT/'results')
    ap.add_argument('--workers',type=int,default=min(6,os.cpu_count() or 1))
    ap.add_argument('--eval-workers',type=int,default=1,help='Parallel official evaluations inside one case. Above 1, selection runs in this process so the pools are not nested.')
    ap.add_argument('--initial-workers',type=int,default=2,help='With --wait-baselines, limit selection workers until all baselines finish')
    ap.add_argument('--wait-baselines',action='store_true',help='A separate baseline process is running; dispatch only completed cases')
    ap.add_argument('--mode',choices=['baseline','full','aggregate'],default='full')
    ap.add_argument('--cases',nargs='*',help='e.g. case_001 case_014; omitted means all official cases')
    ap.add_argument('--cores',nargs='+',type=int,default=[1,2,3,4,5])
    ap.add_argument('--budget',default='standard')
    ap.add_argument('--problems',nargs='+',type=int,default=[1,2],help='Problems to select. Problem 3 is evaluated only when 2 is selected.')
    args=ap.parse_args()
    if args.eval_workers < 1:
        ap.error('--eval-workers must be >= 1')
    if any(p not in (1,2) for p in args.problems):
        ap.error('--problems accepts 1 and 2; problem 3 is evaluated only when 2 is selected')
    seen=set();problems=[]
    for p in args.problems:
        if p not in seen:
            seen.add(p);problems.append(p)
    args.problems=problems
    args.output.mkdir(parents=True,exist_ok=True)
    if args.mode=='aggregate': print('rows',aggregate(args.output));return
    cases=sorted(args.data.glob('case_*.json'))
    if args.cases: cases=[p for p in cases if p.stem in args.cases]
    cases.sort(key=lambda p:p.stat().st_size,reverse=True)
    if 'ALLIN2_CASE_START' not in os.environ:
        os.environ['ALLIN2_CASE_START']=str(time.perf_counter())
    if args.mode=='full':check_manifest(args.output,args.budget,args.data,args.problems)
    env=dict(python=sys.version,platform=platform.platform(),processor=platform.processor(),logical_cpus=os.cpu_count(),workers=args.workers,eval_workers=args.eval_workers,initial_workers=args.initial_workers,budget=args.budget,problems=args.problems)
    write_json(args.output/('baseline_environment.json' if args.mode=='baseline' else 'execution_environment.json'),env)
    started=time.perf_counter(); errors=[]
    if args.eval_workers > 1:
        if args.mode=='baseline' or not args.wait_baselines:
            for i,p in enumerate(cases,1):
                try:
                    baseline_job(str(p),str(args.output))
                    print(f'[baseline {i}/{len(cases)}] {p.stem}: OK, elapsed {time.perf_counter()-started:.1f}s',flush=True)
                except Exception as error:
                    errors.append(dict(job=p.stem,error=str(error),traceback=traceback.format_exc()))
                    print(f'[baseline {i}/{len(cases)}] {p.stem}: ERROR {error}',flush=True)
                write_json(args.output/'run_errors.json',errors)
        if args.mode=='full' and not errors:
            errors=_run_cases_inline(cases,args)
        if errors: raise SystemExit(1)
        print(f'Finished in {time.perf_counter()-started:.1f}s; rows={aggregate(args.output)}',flush=True)
        return
    with cf.ProcessPoolExecutor(max_workers=args.workers) as pool:
        if args.mode=='baseline' or not args.wait_baselines:
            futures={pool.submit(baseline_job,str(p),str(args.output)):p.stem for p in cases}
            for i,future in enumerate(cf.as_completed(futures),1):
                label=futures[future]
                try:
                    future.result();print(f'[baseline {i}/{len(futures)}] {label}: OK, elapsed {time.perf_counter()-started:.1f}s',flush=True)
                except Exception as error:
                    errors.append(dict(job=label,error=str(error),traceback=traceback.format_exc()))
                    print(f'[baseline {i}/{len(futures)}] {label}: ERROR {error}',flush=True)
                write_json(args.output/'run_errors.json',errors)
        if args.mode=='full' and not errors:errors=run_selected_dispatch(pool,cases,args)
    if errors: raise SystemExit(1)
    print(f'Finished in {time.perf_counter()-started:.1f}s; rows={aggregate(args.output)}',flush=True)

if __name__=='__main__':
    main()
