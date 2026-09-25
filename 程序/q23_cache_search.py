"""Timed cache-toggle search; no new candidate family or cached global time.

Joint proposals follow identical RNG/acceptance rules in both arms. Full-result
digests allow common-prefix audits. Final replay always disables preparation reuse.
"""
import argparse,contextlib,copy,gzip,json,multiprocessing as mp,random,time,traceback
from pathlib import Path
from q1_io import sha,write_json
from q2_timed_portfolio import atomic,objective,generate
from q2_evaluator import key

def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))

def peak_rss():
    try:
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
    except ImportError:return None

def worker(args,deadline):
    from q3_solver import load,evaluate as q3,audit
    from q2_evaluator import evaluate as q2
    from q2_physical import PhysicalScorer
    from q1_structural_seeds import GraphModel,_component_plan
    from q2_solver import SceneBGraph
    from q23_preparation_reuse import SerializedPreparationReuse
    out=Path(args['output']);rows=[];cache=None;stages={};best=result=None
    started=time.monotonic()
    try:
        s,d,c,provenance=load();raw=read(args['graph']);q=args['problem']
        def score(p):return q2(raw,p,s,d) if q==2 else q3(raw,p,s,d,c)
        def physical(p,r):
            if q==3:audit(raw,p,r,s,d)
            else:PhysicalScorer(raw,s,d).actual_lifetimes(p,r)
        @contextlib.contextmanager
        def original():
            wrappers={n:getattr(cache.module,n) for n in cache.original} if cache else {}
            try:
                if cache:
                    for n,fn in cache.original.items():setattr(cache.module,n,fn)
                yield
            finally:
                if cache:
                    for n,fn in wrappers.items():setattr(cache.module,n,fn)
        def checkpoint(p,r,label):
            write_json(out/(label+'.plan.json'),p)
            with gzip.open(out/(label+'.evaluation.json.gz'),'wt',encoding='utf-8') as f:json.dump(r,f)
            atomic(out/'verified.json',dict(plan=label+'.plan.json',evaluation=label+'.evaluation.json.gz',makespan=r['makespan'],added=objective(r)[1],plan_sha256=key(p),official_original=True))
        t=time.monotonic()
        if args['plan']:seed=read(args['plan']);m=None
        else:
            m=GraphModel(raw,s,dict(task_cross_core_wait_cycles=d,task_same_core_wait_cycles=0))
            seed=_component_plan(m,5,'pipe',True)
        stages['seed_seconds']=time.monotonic()-t
        atomic(out/'identity.json',dict(problem=q,mode=args['mode'],input_sha256=sha(Path(args['graph']).read_bytes()),seed_sha256=key(seed),seed_mode='imported_latest' if args['plan'] else 'cold_pipe_components',provenance=provenance,stages=stages))
        t=time.monotonic();anchor=score(seed);stages['anchor_score_seconds']=time.monotonic()-t
        t=time.monotonic();physical(seed,anchor);stages['anchor_audit_seconds']=time.monotonic()-t
        checkpoint(seed,anchor,'anchor');best=copy.deepcopy(seed);result=anchor
        # Reserve observed ORIGINAL verification cost, independent of cache speed.
        reserve=max(.2*args['seconds'],1.6*(stages['anchor_score_seconds']+stages['anchor_audit_seconds']))
        search_end=deadline-reserve
        atomic(out/'phase.json',dict(stage='verified_anchor',stages=stages,reserve_seconds=reserve))
        if time.monotonic()<search_end:
            t=time.monotonic();m=m or GraphModel(raw,s,dict(task_cross_core_wait_cycles=d,task_same_core_wait_cycles=0));g=SceneBGraph(raw,s,d)
            stages['model_seconds']=time.monotonic()-t
            rng=random.Random(args['seed']);seen={key(seed)};last=stages['anchor_score_seconds']
            cache=SerializedPreparationReuse(q,max_bytes=args['cache_mib']*1024**2) if args['mode']=='on' else None
            with cache if cache else contextlib.nullcontext():
                for i in range(args['max_proposals']):
                    if time.monotonic()+1.5*last>=search_end:break
                    t=time.monotonic();row=dict(index=i,incumbent=key(best))
                    try:
                        p=generate('joint',m,g,best,5,rng,i);h=key(p);row.update(plan_sha256=h,generation_seconds=time.monotonic()-t)
                        if h in seen:row.update(status='duplicate',seconds=time.monotonic()-t)
                        else:
                            seen.add(h);e=time.monotonic();r=score(p);last=time.monotonic()-e
                            digest=sha(json.dumps(r,sort_keys=True,separators=(',',':')).encode())
                            accept=objective(r)<objective(result)
                            row.update(status='ok',score_seconds=last,result_sha256=digest,makespan=r['makespan'],added=objective(r)[1],accepted=accept)
                            if accept:best,result=p,r
                            row['seconds']=time.monotonic()-t
                    except (ValueError,RuntimeError) as exc:row.update(status='invalid',error=str(exc),seconds=time.monotonic()-t)
                    rows.append(row)
                    atomic(out/'search.json',dict(rows=rows,cache_stats=dict(cache.stats) if cache else {},peak_rss_bytes=peak_rss(),stages=stages,reserve_seconds=reserve))
                t=time.monotonic()
                with original():
                    replay=score(best);assert replay==result;physical(best,replay)
                stages['final_original_verify_seconds']=time.monotonic()-t
                checkpoint(best,replay,'final')
        else:
            # Anchor itself came from the original evaluator and physical audit.
            stages['final_original_verify_seconds']=0
        atomic(out/'details.json',dict(stages=stages,anchor=objective(anchor),selected=objective(result),cache_stats=dict(cache.stats) if cache else {},peak_rss_bytes=peak_rss(),rows=rows,reserve_seconds=reserve,worker_seconds=time.monotonic()-started,complete=True))
    except Exception:(out/'error.txt').write_text(traceback.format_exc(),encoding='utf-8')

def run(args):
    if not 0<args['seconds']<=590 or args['cache_mib']<=0 or args['max_proposals']<0:raise ValueError('Invalid limits')
    started=time.monotonic();out=Path(args['output']);out.mkdir(parents=True,exist_ok=False)
    p=mp.get_context('spawn').Process(target=worker,args=(args,started+args['seconds']));p.start();rss=0
    while p.is_alive() and time.monotonic()<started+args['seconds']:
        try:
            for line in Path(f'/proc/{p.pid}/status').read_text().splitlines():
                if line.startswith(('VmRSS:','VmHWM:')):rss=max(rss,int(line.split()[1])*1024)
        except (FileNotFoundError,PermissionError):pass
        p.join(min(.25,max(0,started+args['seconds']-time.monotonic())))
    stopped=p.is_alive()
    if stopped:p.terminate();p.join(2)
    if p.is_alive():p.kill();p.join(2)
    summary=dict(arguments=args,total_seconds=time.monotonic()-started,deadline_stop=stopped,error=(out/'error.txt').exists(),complete=(out/'details.json').exists(),valid=(out/'verified.json').exists(),peak_child_rss_bytes=rss or None,worker_exitcode=p.exitcode,
        timing='Raw JSON to verified solution includes seed construction if plan omitted; fixed T1 excluded as scoring reference. Imported historical seed generation excluded and not recoverable from this timing.')
    if summary['valid']:summary.update(read(out/'verified.json'))
    atomic(out/'summary.json',summary);return summary

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--problem',required=True,type=int,choices=[2,3]);p.add_argument('--graph',required=True);p.add_argument('--plan');p.add_argument('--output',required=True);p.add_argument('--mode',choices=['off','on'],required=True);p.add_argument('--seconds',type=float,default=590);p.add_argument('--seed',type=int,default=0);p.add_argument('--max-proposals',type=int,default=96);p.add_argument('--cache-mib',type=int,default=32)
    print(json.dumps(run(vars(p.parse_args()))))
