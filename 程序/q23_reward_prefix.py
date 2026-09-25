"""Deterministic reward-per-attempt weights with protected exploration.

No historical candidate plan/log is read. Initial menus are unchanged; structure
sets fixed family frequencies. More time extends the SAME trajectory, subject to
the same proposal cap. This does not reproduce the old time-adaptive policy.
"""
import argparse,copy,gzip,json,random,time,traceback
from collections import Counter
from pathlib import Path
from unittest.mock import patch
from q1_io import write_json
from q2_evaluator import key
from q2_timed_portfolio import atomic,objective,generate,family_weights
from q23_order_portfolio import worker as ordered_worker
from q23_cache_search import run as supervised_run
from q23_stable_prefix import worker as fixed_worker

def sequence(problem,model):
    weights=family_weights(model);weights['frontier']=1
    if len(model.components)>1:weights['packing']=2
    if problem==3:weights['cache']=2
    order=[f for f in ['order','remap','insert','granularity','frontier','packing','joint','cache'] if f in weights]
    cycle=[f for layer in range(max(weights.values())) for f in order if weights[f]>layer]
    prefix=(['joint']*4 if problem==2 else ['cache','joint']*4)+cycle
    return prefix,cycle

def reward(before,after):
    if after[0]<before[0]:return (before[0]-after[0])/max(1,before[0])
    if after[0]==before[0] and after[1]<before[1]:return .001*(before[1]-after[1])/max(1,before[1])
    return 0.

def choose(index,prefix,cycle,counts,gains,rng):
    if index<len(prefix):return prefix[index],None
    j=index-len(prefix);prior=Counter(cycle);families=list(prior)
    weights={f:prior[f]*(1+min(8.,100*gains[f]/max(1,counts[f]))) for f in families}
    # Half of extension slots retain a fixed structural exploration sequence.
    if j%2==0:return cycle[(j//2)%len(cycle)],weights
    return rng.choices(families,[weights[f] for f in families])[0],weights

def search_worker(args,deadline):
    import q2_timed_portfolio,q3_solver
    from q2_solver import SceneBGraph
    from q1_structural_seeds import GraphModel
    from q2_reserve_shared import menu
    from q2_bottleneck_j import pool as ordinary_pool
    from q3_neighborhood import pool as cache_pool
    out=Path(args['output']);rows=[];proposals=[];seen=set();best=result=None;counts=Counter();menus={}
    started=time.monotonic();rng=random.Random(args['seed']);selection_rng=random.Random(args['seed']+0x51EC70);gains=Counter();q=args['problem']
    def save():
        atomic(out/'search.json',dict(evaluations=rows,proposals=proposals,counts=dict(counts),gains=dict(gains),policy='attempt_reward_v1'))
    try:
        settings,delay,cache,prov=q3_solver.load();raw=json.loads(Path(args['graph']).read_text(encoding='utf-8'))
        g=SceneBGraph(raw,settings,delay);m=GraphModel(raw,settings,dict(task_cross_core_wait_cycles=delay,task_same_core_wait_cycles=0))
        def assess(plan,label):
            nonlocal best,result
            h=key(plan);t=time.monotonic()
            if h in seen:
                rows.append(dict(name=label,plan_sha256=h,status='duplicate'));save();return
            seen.add(h)
            try:
                r=q2_timed_portfolio.evaluate(raw,plan,settings,delay) if q==2 else q3_solver.evaluate(raw,plan,settings,delay,cache)
                if q==3:q3_solver.audit_cache(r)
                accepted=result is None or objective(r)<objective(result)
                if accepted:
                    best,result=copy.deepcopy(plan),r;stem=f'accepted_{len(rows):03}'
                    write_json(out/(stem+'.plan.json'),plan)
                    with gzip.open(out/(stem+'.evaluation.json.gz'),'wt',encoding='utf-8') as f:json.dump(r,f)
                    atomic(out/'verified.json',dict(plan=stem+'.plan.json',evaluation=stem+'.evaluation.json.gz',plan_sha256=h))
                rows.append(dict(name=label,status='ok',plan_sha256=h,makespan=r['makespan'],added_copy_bytes=objective(r)[1],accepted=accepted,seconds=time.monotonic()-t))
            except (ValueError,RuntimeError) as e:rows.append(dict(name=label,status='invalid',plan_sha256=h,error=str(e),seconds=time.monotonic()-t))
            save()
        prefix,cycle=sequence(q,m)
        atomic(out/'identity.json',dict(problem=q,arguments=args,provenance=prov,prefix=prefix,extension_cycle=cycle,policy='attempt_reward_v1'))
        if q==2:
            migration=json.loads(Path(args['migration']).read_text(encoding='utf-8'))
            assess(migration,'migration_B')
            whole=dict(node_to_subgraph={str(u):0 for u in g.ops},core_schedules=[[0]]+[[] for _ in range(args['cores']-1)])
            _,more=menu(raw,settings,delay,args['cores'],migration,{})
            for name,plan in [('whole',whole)]+more:
                if time.monotonic()>=deadline:return
                assess(plan,name)
            for item in ordinary_pool(g,best,None,budget=4):
                if time.monotonic()>=deadline:return
                assess(item['plan'],'ordinary_J')
        else:
            assess(json.loads(Path(args['seed_plan']).read_text(encoding='utf-8')),'latest_Q2_in_L2')
            if args.get('anchor') and time.monotonic()<deadline:assess(json.loads(Path(args['anchor']).read_text(encoding='utf-8')),'previous_Q3_anchor')
        for i in range(args['max_proposals']):
            recent=[x['seconds'] for x in rows if x['status']=='ok'][-4:]
            if deadline-time.monotonic()<max(.5,1.3*max(recent,default=.1)):break
            family,weights=choose(i,prefix,cycle,counts,gains,selection_rng)
            before=objective(result)
            step=counts[family];counts[family]+=1;t=time.monotonic()
            row=dict(index=i,family=family,step=step,phase='base' if i<len(prefix) else 'append',incumbent=key(best),selection_weights=weights)
            try:
                if family=='cache':
                    h=key(best)
                    if h not in menus:menus[h]=iter(cache_pool(g,best,q3_solver.cache_diagnostic(result),budget=24))
                    item=next(menus[h],None)
                    if item is None:row['status']='exhausted';proposals.append(row);save();continue
                    plan=item['plan']
                else:plan=generate(family,m,g,best,args['cores'],rng,step)
                row['plan_sha256']=key(plan);assess(plan,family);row['status']=rows[-1]['status'];row['accepted']=rows[-1].get('accepted',False)
            except (ValueError,RuntimeError) as e:row.update(status='generation_invalid',error=str(e))
            row['reward']=reward(before,objective(result));gains[family]+=row['reward']
            row['seconds']=time.monotonic()-t;proposals.append(row);save()
    except Exception:(out/'error.txt').write_text(traceback.format_exc(),encoding='utf-8')

def worker(args,deadline):
    import q2_timed_portfolio,q3_timed_combination
    if args['policy']!='reward':fixed_worker(args,deadline)
    else:
        with patch.object(q2_timed_portfolio,'worker',search_worker),patch.object(q3_timed_combination,'worker',search_worker):
            ordered_worker(args,deadline)
        path=Path(args['output'])/'details.json'
        if path.exists():
            data=json.loads(path.read_text(encoding='utf-8'))
            data['policy']='attempt_reward_v1; reward per attempt, 50% fixed exploration, independent selection RNG; elapsed time only stops search'
            atomic(path,data)

def run(args):
    import q23_cache_search
    with patch.object(q23_cache_search,'worker',worker):return supervised_run(args)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--problem',type=int,required=True,choices=[2,3]);p.add_argument('--graph',required=True);p.add_argument('--output',required=True)
    p.add_argument('--migration');p.add_argument('--seed-plan');p.add_argument('--anchor');p.add_argument('--ordering-prepare',action='store_true')
    p.add_argument('--policy',choices=['legacy','stable','reward'],default='reward');p.add_argument('--seconds',type=float,default=590);p.add_argument('--cores',type=int,default=5);p.add_argument('--seed',type=int,default=0);p.add_argument('--max-proposals',type=int,default=384)
    a=vars(p.parse_args());a.update(reuse=True,cache_mib=32);print(json.dumps(run(a)))
