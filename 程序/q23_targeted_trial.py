"""Small frozen-pool comparisons: budget includes final original replay/audit."""
import argparse,copy,gzip,json,multiprocessing as mp,time,traceback
from pathlib import Path
from q1_io import write_json
from q2_timed_portfolio import atomic,objective
from q2_evaluator import key

def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))

def worker(args,deadline):
    from q3_solver import load,evaluate as q3,audit,audit_cache
    from q2_evaluator import evaluate as q2
    from q2_physical import PhysicalScorer
    from q23_targeted_candidates import ordinary,waiting,cache_order,unique
    out=Path(args['output']);log=[]
    try:
        s,d,c,_=load();raw=read(args['graph']);seed=read(args['plan']);problem=args['problem']
        def evaluate(p):return q2(raw,p,s,d) if problem==2 else q3(raw,p,s,d,c)
        def verify(p,r):
            replay=evaluate(p);assert replay==r
            if problem==3:audit(raw,p,replay,s,d)
            else:PhysicalScorer(raw,s,d).actual_lifetimes(p,replay)
        def checkpoint(p,r,label):
            write_json(out/(label+'.plan.json'),p)
            with gzip.open(out/(label+'.evaluation.json.gz'),'wt',encoding='utf-8') as f:json.dump(r,f)
            atomic(out/'verified.json',dict(plan=label+'.plan.json',evaluation=label+'.evaluation.json.gz',makespan=r['makespan'],added=objective(r)[1],replayed=True))
        t=time.monotonic();anchor=evaluate(seed);verify(seed,anchor);checkpoint(seed,anchor,'fallback')
        anchor_seconds=time.monotonic()-t;best=copy.deepcopy(seed);result=anchor
        # At least 30% reserved; observed full anchor replay/audit informs reserve.
        reserve=max(.3*args['seconds'],1.5*anchor_seconds);search_end=deadline-reserve
        started=time.monotonic();diagnostic={}
        if problem==2:
            base=ordinary(raw,seed,s,d,16)
            if args['arm']=='guided':
                extra,diagnostic=waiting(raw,seed,anchor,s,d,8);candidates=unique(base[:8]+extra,seed,16)
            else:candidates=base
        else:candidates,diagnostic=cache_order(raw,seed,anchor,s,d,args['arm']=='guided',16)
        generation_seconds=time.monotonic()-started
        atomic(out/'pool.json',dict(generation_seconds=generation_seconds,diagnostic=diagnostic,candidates=[dict(plan=p,label=n,sha256=key(p)) for p,n in candidates]))
        last=anchor_seconds/2
        for p,label in candidates:
            if time.monotonic()+1.5*last>=search_end:break
            t=time.monotonic()
            try:
                r=evaluate(p);last=time.monotonic()-t;accept=objective(r)<objective(result)
                log.append(dict(label=label,status='ok',makespan=r['makespan'],added=objective(r)[1],accepted=accept,same_cycle_less_bytes=accept and r['makespan']==result['makespan'],seconds=last))
                if accept:best,result=p,r
            except (ValueError,RuntimeError) as e:log.append(dict(label=label,status='invalid',error=str(e),seconds=time.monotonic()-t))
            atomic(out/'search.json',log)
        t=time.monotonic();verify(best,result);checkpoint(best,result,'final')
        atomic(out/'details.json',dict(anchor=objective(anchor),selected=objective(result),generation_seconds=generation_seconds,anchor_verify_seconds=anchor_seconds,final_verify_seconds=time.monotonic()-t,reserved_seconds=reserve,evaluations=log,diagnostic=diagnostic,final_replay_complete=True))
    except Exception:(out/'error.txt').write_text(traceback.format_exc(),encoding='utf-8')

def run(args):
    started=time.monotonic();out=Path(args['output']);out.mkdir(parents=True,exist_ok=False)
    proc=mp.get_context('spawn').Process(target=worker,args=(args,started+args['seconds']));proc.start();proc.join(max(0,args['seconds']-(time.monotonic()-started)))
    stopped=proc.is_alive()
    if stopped:proc.terminate();proc.join(2)
    if proc.is_alive():proc.kill();proc.join(2)
    r=dict(arguments=args,total_seconds=time.monotonic()-started,deadline_stop=stopped,error=(out/'error.txt').exists(),complete=(out/'details.json').exists(),valid=(out/'verified.json').exists())
    if r['valid']:r.update(read(out/'verified.json'))
    atomic(out/'summary.json',r);return r

def reuse_benchmark(folder,problem,graph,seed):
    from q3_solver import load,evaluate as q3
    from q2_evaluator import evaluate as q2
    from q23_preparation_reuse import PreparationReuse
    s,d,c,_=load();raw=read(graph);base=read(seed)
    def ev(p,settings=s):return q2(raw,p,settings,d) if problem==2 else q3(raw,p,settings,d,c)
    pool=read(folder/'pool.json')['candidates'];plans=[base]+[x['plan'] for x in pool[:3]]
    rows=[]
    # Complete ordered input fixed; two passes separately expose cold and warm cost.
    for repeat in range(2):
        with PreparationReuse(problem) as reuse:
            for phase in ['cold','warm']:
                for i,p in enumerate(plans):
                    # Disable wrappers for original replay, then restore this cache.
                    wrappers={n:getattr(reuse.module,n) for n in reuse.original}
                    for n,fn in reuse.original.items():setattr(reuse.module,n,fn)
                    try:t=time.perf_counter();a=ev(p);plain=time.perf_counter()-t
                    finally:
                        for n,fn in wrappers.items():setattr(reuse.module,n,fn)
                    t=time.perf_counter();b=ev(p);cached=time.perf_counter()-t;assert a==b
                    rows.append(dict(repeat=repeat,phase=phase,candidate=i,equal=True,original_seconds=plain,reuse_seconds=cached,stats=dict(reuse.stats)))
    atomic(folder/'reuse_benchmark.json',dict(rows=rows,caveat='Warm pass intentionally repeats pool; not expected production hit rate. Whole global DDR/L2 simulation always rerun.'))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--problem',type=int,choices=[2,3],required=True);p.add_argument('--graph',required=True);p.add_argument('--plan',required=True);p.add_argument('--output',required=True);p.add_argument('--arm',choices=['control','guided'],default='guided');p.add_argument('--seconds',type=float,default=90);p.add_argument('--benchmark',action='store_true')
    a=vars(p.parse_args());bench=a.pop('benchmark')
    if bench:reuse_benchmark(Path(a['output']),a['problem'],a['graph'],a['plan'])
    else:print(json.dumps(run(a)))
