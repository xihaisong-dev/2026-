"""Preserve all16 base candidates before diagnostics; refill unique extras to24."""
import argparse,copy,gzip,json,multiprocessing as mp,time,traceback
from pathlib import Path
from q1_io import write_json
from q2_timed_portfolio import atomic,objective
from q2_evaluator import key

def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))

def refill(base,extra,seed,limit=24):
    from q23_targeted_candidates import unique
    # Base16 is immutable; only the remaining eight opportunities are guided.
    return unique(base[:16]+extra+base[16:],seed,limit)

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
        if problem==2:base=ordinary(raw,seed,s,d,24)
        else:base,_=cache_order(raw,seed,anchor,s,d,False,24)
        candidates=base[:16];protected_keys=[key(p) for p,_ in candidates]
        generation_seconds=time.monotonic()-started
        atomic(out/'pool.json',dict(generation_seconds=generation_seconds,diagnostic=diagnostic,candidates=[dict(plan=p,label=n,sha256=key(p)) for p,n in candidates]))
        last=anchor_seconds/2
        def assess(p,label):
            nonlocal last,best,result
            if time.monotonic()+1.5*last>=search_end:return False
            t=time.monotonic()
            try:
                r=evaluate(p);last=time.monotonic()-t;accept=objective(r)<objective(result)
                log.append(dict(label=label,status='ok',makespan=r['makespan'],added=objective(r)[1],accepted=accept,same_cycle_less_bytes=accept and r['makespan']==result['makespan'],seconds=last))
                if accept:best,result=p,r
            except (ValueError,RuntimeError) as e:log.append(dict(label=label,status='invalid',error=str(e),seconds=time.monotonic()-t))
            atomic(out/'search.json',log)
            return True
        prefix_complete=True
        for p,label in candidates:
            if not assess(p,label):prefix_complete=False;break
        if prefix_complete and time.monotonic()+1.5*last<search_end:
            t=time.monotonic();extra=[]
            if args['arm']=='guided':
                if problem==2:extra,diagnostic=waiting(raw,seed,anchor,s,d,8)
                else:extra,diagnostic=cache_order(raw,seed,anchor,s,d,True,8)
            generation_seconds+=time.monotonic()-t
            candidates=refill(base,extra,seed)
            assert [key(p) for p,_ in candidates[:len(protected_keys)]]==protected_keys
            for p,label in candidates[len(protected_keys):]:
                if not assess(p,label):break
        atomic(out/'pool.json',dict(generation_seconds=generation_seconds,diagnostic=diagnostic,protected_keys=protected_keys,
            prefix_complete=prefix_complete,candidates=[dict(plan=p,label=n,sha256=key(p)) for p,n in candidates]))
        t=time.monotonic();verify(best,result);checkpoint(best,result,'final')
        atomic(out/'details.json',dict(anchor=objective(anchor),selected=objective(result),generation_seconds=generation_seconds,anchor_verify_seconds=anchor_seconds,final_verify_seconds=time.monotonic()-t,reserved_seconds=reserve,evaluations=log,diagnostic=diagnostic,protected_keys=protected_keys,prefix_complete=prefix_complete,final_replay_complete=True))
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
    from q23_preparation_reuse import PreparationReuse,SerializedPreparationReuse
    from contextlib import nullcontext
    s,d,c,_=load();raw=read(graph);base=read(seed)
    def ev(p):return q2(raw,p,s,d) if problem==2 else q3(raw,p,s,d,c)
    candidates=read(folder/'pool.json')['candidates'];plans=[base]+[x['plan'] for x in candidates[:7]]
    assert len({key(p) for p in plans})==len(plans)
    expected=[ev(p) for p in plans];rows=[]
    modes=['original','deepcopy','serialized']
    for repeat in range(3):
        order=modes[repeat:]+modes[:repeat]
        for mode in order:
            context=nullcontext(None) if mode=='original' else (PreparationReuse if mode=='deepcopy' else SerializedPreparationReuse)(problem)
            with context as cache:
                for phase in ['cold_distinct','warm_repeat']:
                    t=time.perf_counter()
                    for plan,target in zip(plans,expected):assert ev(plan)==target
                    rows.append(dict(repeat=repeat,mode=mode,phase=phase,seconds=time.perf_counter()-t,equal_count=len(plans),all_equal=True,stats=dict(cache.stats) if cache else {}))
    atomic(folder/'reuse_benchmark.json',dict(rows=rows,distinct_plans=len(plans),comparison_order='rotating original/deepcopy/serialized over3 repetitions',caveat='Only cold_distinct is nonrepeated candidate stream; warm_repeat is diagnostic. Fresh global simulation on every call.'))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--problem',type=int,choices=[2,3],required=True);p.add_argument('--graph',required=True);p.add_argument('--plan',required=True);p.add_argument('--output',required=True);p.add_argument('--arm',choices=['control','guided'],default='guided');p.add_argument('--seconds',type=float,default=90);p.add_argument('--benchmark',action='store_true')
    a=vars(p.parse_args());bench=a.pop('benchmark')
    if bench:reuse_benchmark(Path(a['output']),a['problem'],a['graph'],a['plan'])
    else:print(json.dumps(run(a)))
