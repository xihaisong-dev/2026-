"""Q2 structural portfolio adapted to actual FIFO-L2 events, bounded wall time."""
import argparse,copy,gzip,json,multiprocessing as mp,random,time,traceback
from pathlib import Path
from collections import defaultdict
from q1_io import write_json,sha
from q2_timed_portfolio import atomic,objective,generate,family_weights
from q2_evaluator import key


def worker(args,deadline):
    from q3_solver import load,evaluate,audit_cache,cache_diagnostic
    from q3_neighborhood import pool
    from q2_solver import SceneBGraph
    from q1_structural_seeds import GraphModel
    out=Path(args['output']);rows=[];seen=set();best=result=None
    try:
        s,d,c,provenance=load();raw=json.loads(Path(args['graph']).read_text(encoding='utf-8'))
        atomic(out/'identity.json',dict(problem=3,cache=c,provenance=provenance,
            input_sha256=sha(Path(args['graph']).read_bytes()),seed_sha256=sha(Path(args['seed_plan']).read_bytes()),
            anchor_sha256=sha(Path(args['anchor']).read_bytes()) if args['anchor'] else None,
            warm_start=True,arguments=args))
        def assess(p,name):
            nonlocal best,result
            h=key(p);started=time.monotonic()
            if h in seen:return 0.
            seen.add(h)
            try:
                r=evaluate(raw,p,s,d,c);audit_cache(r)
                gain=max(0.,(result['makespan']-r['makespan'])/result['makespan']) if result else 0.
                accept=result is None or objective(r)<objective(result)
                if accept:
                    stem=f'accepted_{len(rows):03}'
                    write_json(out/(stem+'.plan.json'),p)
                    with gzip.open(out/(stem+'.evaluation.json.gz'),'wt',encoding='utf-8') as f:json.dump(r,f)
                    atomic(out/'verified.json',dict(plan=stem+'.plan.json',evaluation=stem+'.evaluation.json.gz',
                        makespan=r['makespan'],added_copy_bytes=objective(r)[1],plan_sha256=h,official_problem=3))
                    best,result=copy.deepcopy(p),r
                rows.append(dict(name=name,status='ok',accepted=accept,makespan=r['makespan'],
                    added_copy_bytes=objective(r)[1],hit_bytes=r['cache_stats']['hit_bytes'],
                    plan_sha256=h,seconds=time.monotonic()-started))
            except (ValueError,RuntimeError) as e:
                gain=0.;rows.append(dict(name=name,status='invalid',error=str(e),plan_sha256=h,seconds=time.monotonic()-started))
            atomic(out/'search.json',dict(evaluations=rows));return gain
        assess(json.loads(Path(args['seed_plan']).read_text(encoding='utf-8')),'latest_Q2_in_L2')
        if args['anchor'] and time.monotonic()<deadline:
            assess(json.loads(Path(args['anchor']).read_text(encoding='utf-8')),'previous_Q3_anchor')
        if args['arm']=='seed_only':return
        g=SceneBGraph(raw,s,d);m=GraphModel(raw,s,dict(task_cross_core_wait_cycles=d,task_same_core_wait_cycles=0))
        weights=family_weights(m) if args['arm']=='combined' else {'joint':1}
        weights['cache']=2
        if args['arm']=='combined':
            weights['frontier']=1
            if len(m.components)>1:weights['packing']=2
        rng=random.Random(args['seed']);counts=defaultdict(int);gains=defaultdict(float);spent=defaultdict(float)
        menus={};protected_until=time.monotonic()+.4*max(0,deadline-time.monotonic())
        for it in range(args['max_proposals']):
            costs=[r['seconds'] for r in rows if r['status']=='ok'][-4:]
            if deadline-time.monotonic()<max(.5,1.3*max(costs,default=.1)):break
            unexplored=[f for f in weights if not counts[f]]
            if it<16 and time.monotonic()<protected_until:family='joint' if it%2 else 'cache'
            elif unexplored:family=unexplored[0]
            else:family=rng.choices(list(weights),[weights[f]*(1+min(8,100*gains[f]/max(.1,spent[f]))) for f in weights])[0]
            index=counts[family];counts[family]+=1;started=time.monotonic()
            try:
                if family=='cache':
                    h=key(best)
                    if h not in menus:menus[h]=iter(pool(g,best,cache_diagnostic(result),budget=24))
                    item=next(menus[h],None)
                    if item is None:continue
                    candidate=item['plan']
                else:candidate=generate(family,m,g,best,args['cores'],rng,index)
                gains[family]+=assess(candidate,family)
            except (ValueError,RuntimeError) as e:
                rows.append(dict(name=family,status='generation_invalid',error=str(e)))
            finally:spent[family]+=time.monotonic()-started
        atomic(out/'search.json',dict(evaluations=rows,family_counts=dict(counts),family_gain=dict(gains),family_seconds=dict(spent)))
    except Exception:(out/'error.txt').write_text(traceback.format_exc(),encoding='utf-8')


def run(graph,seed_plan,output,anchor=None,cores=5,seconds=590,arm='combined',seed=0,max_proposals=96):
    if cores not in range(2,6) or not 0<seconds<=590 or arm not in ['seed_only','local','combined']:raise ValueError('Invalid budget/arm/cores')
    started=time.monotonic();out=Path(output);out.mkdir(parents=True,exist_ok=False)
    args=dict(graph=str(Path(graph).resolve()),seed_plan=str(Path(seed_plan).resolve()),output=str(out.resolve()),
        anchor=str(Path(anchor).resolve()) if anchor else None,cores=cores,seconds=seconds,arm=arm,seed=seed,max_proposals=max_proposals)
    p=mp.get_context('spawn').Process(target=worker,args=(args,started+seconds));p.start()
    p.join(max(0,seconds-(time.monotonic()-started)));stopped=p.is_alive()
    if stopped:p.terminate();p.join(2)
    if p.is_alive():p.kill();p.join(2)
    summary=dict(arguments=args,seconds=time.monotonic()-started,deadline_stop=stopped,worker_exitcode=p.exitcode,
        worker_error=(out/'error.txt').exists(),status='ok' if (out/'verified.json').exists() else 'no_verified_solution',
        source_sha256=sha(Path(__file__).read_bytes()))
    if (out/'verified.json').exists():summary.update(json.loads((out/'verified.json').read_text(encoding='utf-8')))
    atomic(out/'summary.json',summary);return summary


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('graph');p.add_argument('--seed-plan',required=True);p.add_argument('--anchor')
    p.add_argument('--output',required=True);p.add_argument('--cores',type=int,default=5);p.add_argument('--seconds',type=float,default=590)
    p.add_argument('--arm',choices=['seed_only','local','combined'],default='combined');p.add_argument('--seed',type=int,default=0)
    p.add_argument('--max-proposals',type=int,default=96)
    print(json.dumps(run(**vars(p.parse_args())),ensure_ascii=False))
