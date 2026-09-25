"""Q1 staged wall-clock search with exact Task preparation reuse and final replay."""
import argparse,gzip,json,math,multiprocessing as mp,shutil,time
from pathlib import Path
from q1_io import PROCESSED,official,verify,sha,write_json
from q1_timed_portfolio import atomic_json

def context(graph):
    raw=json.loads(graph.read_text(encoding='utf-8-sig'));verify();mod=official()
    from evaluation_validation import read_evaluation_config
    settings=read_evaluation_config(str(PROCESSED/'data/config.txt'))
    waits=mod.read_scene_a_config(str(PROCESSED/'data/config.txt'))
    return raw,settings,waits

def original(raw,settings,waits,p):
    return official().evaluate_scene_a(raw,p,settings['bandwidth'],settings['capacity'],
        waits['task_cross_core_wait_cycles'],waits['task_same_core_wait_cycles'])

def read_selected(out,key):
    pointer=json.loads((out/(key+'.json')).read_text(encoding='utf-8'));folder=out/pointer['folder']
    p=json.loads((folder/'plan.json').read_text(encoding='utf-8'))
    with gzip.open(folder/'evaluation.json.gz','rt',encoding='utf-8') as f:r=json.load(f)
    return p,r

def save(out,key,p,r):
    folder=out/f'{key}_{time.time_ns()}';folder.mkdir()
    write_json(folder/'plan.json',p)
    with gzip.open(folder/'evaluation.json.gz','wt',encoding='utf-8') as f:json.dump(r,f,ensure_ascii=False)
    atomic_json(out/(key+'.json'),dict(folder=folder.name,makespan=r['makespan'],added_copy_bytes=r['data_movement_bytes']['added_copy_bytes']))

def value(r):return r['makespan'],r['data_movement_bytes']['added_copy_bytes']

def bootstrap(graph,k,out,seed):
    from q1_experimental import CostGraph
    from q1_timed_candidates import Generator,frontier_mapping,schedule
    raw,settings,waits=context(graph);g=CostGraph(raw,settings,waits,enabled=False);g.fast_costs=True
    gen=Generator(g,k,seed)
    whole=dict(node_to_subgraph={str(u):0 for u in g.ops},core_schedules=[[0]]+[[] for _ in range(k-1)])
    if len(g.ops)>4096:
        mapping=frontier_mapping(g,k,gen.rng,0,target_groups=max(k*4,math.ceil(len(g.ops)/128)),max_ops=256)
        p=schedule(g,mapping,k,gen.rng)
    else:p=gen.propose('vector_packing' if len(gen.groups)>=k else 'frontier',whole)
    t=time.monotonic();r=original(raw,settings,waits,p)
    save(out,'verified',p,r);save(out,'candidate',p,r)
    write_json(out/'bootstrap.json',dict(official_seconds=time.monotonic()-t,ops=len(g.ops)))

def initial(graph,k,out,seed):
    from q1_experimental import solve_experimental
    from q1_submit import BASELINE_FEATURES
    raw,settings,waits=context(graph);p,r=read_selected(out,'candidate');best=value(r)
    def checkpoint(q,s):
        nonlocal best
        if value(s)<best:save(out,'candidate',q,s);best=value(s)
    _,_,stats=solve_experimental(raw,settings,waits,k,12,seed,BASELINE_FEATURES,
        evaluator_backend='counter',initial_plan=p,on_incumbent=checkpoint)
    write_json(out/'initial_search.json',stats)

def search(graph,k,out,seed,deadline,use_structure,use_timeline):
    from q1_experimental import CostGraph
    from q1_timed_candidates import Generator
    from q1_task_reuse import TaskReuseEvaluator
    from q1_staged_moves import profile,weights,timeline_move
    from q1_structural_seeds import canonical_key
    from q1_solver import validate
    raw,settings,waits=context(graph);p,r=read_selected(out,'candidate')
    g=CostGraph(raw,settings,waits,enabled=True);g.fast_costs=True;g.observe(p,r)
    evaluator=TaskReuseEvaluator(raw,g.bandwidth,g.capacity,g.cross,g.same,max_entries=128)
    gen=Generator(g,k,seed);arms=gen.arms+(['timeline_joint'] if use_timeline else [])
    features=profile(g,gen.groups);prior=weights(features,arms) if use_structure else {a:1. for a in arms}
    write_json(out/'structure.json',dict(features=features,priors=prior))
    pulls={a:0 for a in arms};reward={a:0. for a in arms};cost={a:0. for a in arms};seen={canonical_key(p)}
    attempt=0
    with (out/'search.jsonl').open('w',encoding='utf-8') as log:
        while time.monotonic()<deadline:
            arm=min(arms,key=lambda a:pulls[a]) if attempt%5==0 else max(arms,key=lambda a:reward[a]/max(.01,cost[a])+.001*prior[a]*math.sqrt(math.log(attempt+2)/(pulls[a]+1)))
            t=time.monotonic();attempt+=1;pulls[arm]+=1;record=dict(attempt=attempt,arm=arm)
            try:
                q=timeline_move(g,p,r,k,gen.rng,pulls[arm]-1) if arm=='timeline_joint' else gen.propose(arm,p)
                if q is None:record['status']='empty'
                elif canonical_key(q) in seen:record['status']='duplicate'
                else:
                    seen.add(canonical_key(q));validate(g,q);s=evaluator.evaluate(q)
                    accepted=value(s)<value(r)
                    record.update(status='evaluated',makespan=s['makespan'],added_copy_bytes=value(s)[1],accepted=accepted)
                    if accepted:
                        reward[arm]+=max(0,r['makespan']-s['makespan'])/max(1,r['makespan'])
                        save(out,'candidate',q,s);p,r=q,s;g.observe(p,r)
            except (ValueError,RuntimeError) as exc:record.update(status='invalid',error=str(exc))
            elapsed=time.monotonic()-t;cost[arm]+=elapsed;record['seconds']=elapsed
            log.write(json.dumps(record)+'\n');log.flush()
            atomic_json(out/'search_progress.json',dict(attempts=attempt,pulls=pulls,cost_seconds=cost,rewards=reward,reuse=evaluator.stats()))

def replay(graph,k,out,seed):
    raw,settings,waits=context(graph);p,s=read_selected(out,'candidate');_,old=read_selected(out,'verified')
    if value(s)>=value(old):write_json(out/'replay.json',dict(required=False));return
    start=time.monotonic();fresh=original(raw,settings,waits,p)
    equal=json.loads(json.dumps(fresh))==s
    write_json(out/'replay.json',dict(required=True,full_equal=equal,seconds=time.monotonic()-start))
    if not equal:raise RuntimeError('Accelerated result differs from original official output')
    save(out,'verified',p,fresh)

def phase(target,args,deadline):
    start=time.monotonic();p=mp.get_context('spawn').Process(target=target,args=args);p.start()
    p.join(max(0,deadline-time.monotonic()));stopped=p.is_alive()
    if stopped:p.terminate();p.join(.5)
    if p.is_alive():p.kill();p.join()
    return dict(seconds=time.monotonic()-start,interrupted=stopped,exitcode=p.exitcode,error=p.exitcode!=0 and not stopped)

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('graph',type=Path);ap.add_argument('-n','--cores',type=int,choices=range(2,6),required=True)
    ap.add_argument('--seconds',type=float,default=590);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--seed',type=int,default=0)
    ap.add_argument('--no-structure',action='store_true');ap.add_argument('--no-timeline',action='store_true');a=ap.parse_args()
    if not 20<=a.seconds<=600:ap.error('seconds must be in [20,600]')
    start=time.monotonic();out=a.output;out.mkdir(parents=True,exist_ok=False)
    write_json(out/'contract.json',dict(seconds=a.seconds,cores=a.cores,seed=a.seed,mode='cold',graph_sha256=sha(a.graph.read_bytes()),
        source_hashes={p.name:sha(p.read_bytes()) for p in Path(__file__).parent.glob('q1_*.py')},structure=not a.no_structure,timeline=not a.no_timeline,
        accounting='Every accelerated global simulation is a scoring evaluation, not a free proxy.'))
    args=(a.graph,a.cores,out,a.seed);phases={}
    phases['bootstrap']=phase(bootstrap,args,start+min(90,a.seconds*.2))
    if (out/'verified.json').exists():
        boot=json.loads((out/'bootstrap.json').read_text(encoding='utf-8'))
        reserve=max(3,a.seconds*.55 if boot['ops']>4096 else boot['official_seconds']*4)
        search_end=start+a.seconds-2-reserve
        phases['initial']=phase(initial,args,min(start+a.seconds*.2,search_end))
        if time.monotonic()<search_end:
            phases['search']=phase(search,args+(search_end,not a.no_structure,not a.no_timeline),search_end)
        phases['replay']=phase(replay,args,start+a.seconds-2)
        selected=json.loads((out/'verified.json').read_text(encoding='utf-8'))
        shutil.copyfile(out/selected['folder']/'plan.json',out/f'{a.graph.stem}_multicore_res.json')
        run=dict(complete=True,selected=selected,phases=phases,mode='cold',wall_seconds=time.monotonic()-start)
    else:run=dict(complete=False,phases=phases,wall_seconds=time.monotonic()-start)
    run['within_limit']=run['wall_seconds']<=a.seconds;run['worker_error']=any(p['error'] for p in phases.values())
    write_json(out/'run.json',run);print(json.dumps(run),flush=True)
    if not run['complete'] or not run['within_limit'] or run['worker_error']:raise SystemExit(2)

if __name__=='__main__':main()
