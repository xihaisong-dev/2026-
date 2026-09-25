"""Wall-clock bounded Q1 portfolio; every accepted checkpoint is officially scored.

Cold mode starts from the graph, publishes a verified bootstrap, then runs the
adopted search and the adaptive portfolio. Large graphs use the bootstrap in
place of recomputing a whole-graph single-core benchmark. --seed-plan is an
explicit warm-start experiment, never reported as cold reproduction.
"""
import argparse,gzip,json,math,multiprocessing as mp,os,shutil,time
from pathlib import Path
from q1_io import PROCESSED,official,verify,sha,write_json

def atomic_json(path,value):
    tmp=path.with_suffix('.tmp');write_json(tmp,value);os.replace(tmp,path)

def work(graph,cores,output,deadline,seed_plan,seed):
    start=time.monotonic();raw=json.loads(graph.read_text(encoding='utf-8-sig'))
    verify();mod=official()
    from evaluation_validation import read_evaluation_config
    from q1_experimental import CostGraph,solve_experimental
    from q1_submit import BASELINE_FEATURES
    from q1_solver import validate
    from q1_structural_seeds import canonical_key
    from q1_timed_candidates import Generator,frontier_mapping,schedule
    settings=read_evaluation_config(str(PROCESSED/'data/config.txt'));waits=mod.read_scene_a_config(str(PROCESSED/'data/config.txt'))
    def score(plan):
        return mod.evaluate_scene_a(raw,plan,settings['bandwidth'],settings['capacity'],waits['task_cross_core_wait_cycles'],waits['task_same_core_wait_cycles'])
    version=0;best_score=None
    def save(plan,result):
        nonlocal version
        folder=output/f'accepted_{version:04}';folder.mkdir()
        write_json(folder/'plan.json',plan)
        with gzip.open(folder/'evaluation.json.gz','wt',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False)
        atomic_json(output/'incumbent.json',dict(folder=folder.name,makespan=result['makespan'],added_copy_bytes=result['data_movement_bytes']['added_copy_bytes'],elapsed_seconds=time.monotonic()-start))
        version+=1
    if seed_plan:
        plan=json.loads(seed_plan.read_text(encoding='utf-8-sig'));base_stats=None
    else:
        # Establish a verified cold fallback before the older multi-stage search.
        # If that search is interrupted on a large graph, a valid plan survives.
        boot_graph=CostGraph(raw,settings,waits,enabled=False);boot_graph.fast_costs=True
        boot_gen=Generator(boot_graph,cores,seed)
        whole=dict(node_to_subgraph={str(u):0 for u in boot_graph.ops},core_schedules=[[0]]+[[] for _ in range(cores-1)])
        if len(boot_graph.ops)>4096:
            # Bound initial Task size: a union of many components can trigger a
            # very slow official spill schedule before any checkpoint is saved.
            initial=frontier_mapping(boot_graph,cores,boot_gen.rng,0,target_groups=max(cores*4,math.ceil(len(boot_graph.ops)/128)),max_ops=256)
            bootstrap=schedule(boot_graph,initial,cores,boot_gen.rng)
        else:bootstrap=boot_gen.propose('vector_packing' if len(boot_gen.groups)>=cores else 'frontier',whole)
        validate(boot_graph,bootstrap);bootstrap_result=score(bootstrap);save(bootstrap,bootstrap_result)
        write_json(output/'bootstrap.json',dict(makespan=bootstrap_result['makespan'],seconds=time.monotonic()-start))
        checkpoint_score=(bootstrap_result['makespan'],bootstrap_result['data_movement_bytes']['added_copy_bytes'])
        def checkpoint(candidate,fast_result):
            nonlocal checkpoint_score
            value=(fast_result['makespan'],fast_result['data_movement_bytes']['added_copy_bytes'])
            if value<checkpoint_score:
                verified=score(candidate)
                assert verified==fast_result, 'Initial candidate differs from original official replay'
                save(candidate,verified);checkpoint_score=value
        plan,fast,base_stats=solve_experimental(raw,settings,waits,cores,12,seed,BASELINE_FEATURES,evaluator_backend='counter',
            initial_plan=bootstrap if len(boot_graph.ops)>4096 else None,on_incumbent=checkpoint)
        write_json(output/'baseline_search.json',base_stats)
    result=score(plan)
    if not seed_plan:assert result==fast, 'Cold initial solver differs from original official replay'
    write_json(output/'baseline.json',dict(makespan=result['makespan'],added_copy_bytes=result['data_movement_bytes']['added_copy_bytes'],seconds=time.monotonic()-start,mode='warm' if seed_plan else 'cold'))
    if not seed_plan and (bootstrap_result['makespan'],bootstrap_result['data_movement_bytes']['added_copy_bytes'])<(result['makespan'],result['data_movement_bytes']['added_copy_bytes']):
        plan,result=bootstrap,bootstrap_result
    save(plan,result);best_score=(result['makespan'],result['data_movement_bytes']['added_copy_bytes'])
    g=CostGraph(raw,settings,waits,enabled=True);g.fast_costs=True;g.observe(plan,result)
    generator=Generator(g,cores,seed);seen={canonical_key(plan)}
    pulls={a:0 for a in generator.arms};reward={a:0. for a in generator.arms};seconds={a:0. for a in generator.arms}
    calls=0;attempts=0;durations=[]
    with (output/'search.jsonl').open('w',encoding='utf-8') as log:
        while time.monotonic()<deadline-2:
            remaining=deadline-time.monotonic()
            if durations and remaining<max(2,1.5*sum(durations[-4:])/len(durations[-4:])):break
            # Reserve exploration; otherwise choose measured relative gain per CPU second.
            if attempts%5==0 or any(pulls[a]==0 for a in generator.arms):
                arm=min(generator.arms,key=lambda a:(pulls[a],generator.arms.index(a)))
            else:
                arm=max(generator.arms,key=lambda a:reward[a]/max(.01,seconds[a])+.001*math.sqrt(math.log(attempts+1)/(pulls[a]+1)))
            attempts+=1;pulls[arm]+=1;t=time.monotonic();status='ok'
            atomic_json(output/'pending.json',dict(arm=arm,attempt=attempts,stage='generate',elapsed=time.monotonic()-start))
            try:
                candidate=generator.propose(arm,plan)
                if candidate is None:status='empty'
                elif canonical_key(candidate) in seen:status='duplicate'
                else:
                    fingerprint=canonical_key(candidate);seen.add(fingerprint);validate(g,candidate)
                    atomic_json(output/'pending.json',dict(arm=arm,attempt=attempts,stage='official_evaluation',elapsed=time.monotonic()-start))
                    r=score(candidate);calls+=1;elapsed=time.monotonic()-t;durations.append(elapsed)
                    value=(r['makespan'],r['data_movement_bytes']['added_copy_bytes']);gain=max(0,best_score[0]-value[0])/best_score[0]
                    accepted=value<best_score
                    if accepted:save(candidate,r);plan,result=candidate,r;best_score=value;g.observe(plan,result)
                    reward[arm]+=gain
                    log.write(json.dumps(dict(arm=arm,attempt=attempts,status=status,makespan=value[0],added_copy_bytes=value[1],accepted=accepted,relative_gain=gain,seconds=elapsed),ensure_ascii=False)+'\n');log.flush()
            except (ValueError,RuntimeError) as exc:
                status='invalid';log.write(json.dumps(dict(arm=arm,attempt=attempts,status=status,error=str(exc)),ensure_ascii=False)+'\n');log.flush()
            seconds[arm]+=time.monotonic()-t
            if status in ('empty','duplicate'):
                log.write(json.dumps(dict(arm=arm,attempt=attempts,status=status,seconds=time.monotonic()-t))+'\n');log.flush()
            atomic_json(output/'progress.json',dict(official_candidate_calls=calls,attempts=attempts,pulls=pulls,rewards=reward,seconds=seconds,best=best_score))
    write_json(output/'completed.json',dict(official_candidate_calls=calls,attempts=attempts,pulls=pulls,elapsed_seconds=time.monotonic()-start))

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('graph',type=Path);ap.add_argument('-n','--cores',type=int,choices=range(2,6),required=True)
    ap.add_argument('--output',type=Path,required=True);ap.add_argument('--seconds',type=float,default=590);ap.add_argument('--seed-plan',type=Path);ap.add_argument('--seed',type=int,default=0)
    a=ap.parse_args();start=time.monotonic()
    if not 5<=a.seconds<=600:ap.error('seconds must be in [5,600]')
    a.output.mkdir(parents=True,exist_ok=False)
    write_json(a.output/'contract.json',dict(seconds=a.seconds,cores=a.cores,seed=a.seed,mode='warm' if a.seed_plan else 'cold',graph_sha256=sha(a.graph.read_bytes()),
        input_manifest_sha256=sha((PROCESSED/'manifest.json').read_bytes()),config_sha256=sha((PROCESSED/'data/config.txt').read_bytes()),
        source_hashes={p.name:sha(p.read_bytes()) for p in Path(__file__).parent.glob('q1_*.py')},official_scoring='unchanged official evaluate_scene_a for every promoted plan'))
    deadline=start+a.seconds-2
    process=mp.get_context('spawn').Process(target=work,args=(a.graph,a.cores,a.output,deadline,a.seed_plan,a.seed));process.start()
    process.join(max(0,deadline-time.monotonic()))
    timed_out=process.is_alive()
    if timed_out:process.terminate();process.join(1)
    if process.is_alive():process.kill();process.join()
    pointer=a.output/'incumbent.json'
    if pointer.exists():
        incumbent=json.loads(pointer.read_text(encoding='utf-8'));folder=a.output/incumbent['folder']
        shutil.copyfile(folder/'plan.json',a.output/f'{a.graph.stem}_multicore_res.json')
        status=dict(complete=True,worker_deadline_reached=timed_out,worker_exitcode=process.exitcode,worker_error=process.exitcode!=0 and not timed_out,
            baseline_completed=(a.output/'baseline.json').exists(),selected=incumbent,wall_seconds=time.monotonic()-start,mode='warm' if a.seed_plan else 'cold')
    else:status=dict(complete=False,reason='No officially verified incumbent before worker exit',worker_deadline_reached=timed_out,worker_exitcode=process.exitcode,wall_seconds=time.monotonic()-start)
    status['within_limit']=status['wall_seconds']<=a.seconds
    write_json(a.output/'run.json',status);print(json.dumps(status),flush=True)
    if not status['complete'] or not status['within_limit'] or status.get('worker_error'):raise SystemExit(2)

if __name__=='__main__':main()
