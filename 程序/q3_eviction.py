"""Exact FIFO eviction witness -> legal consumer/source/joint order proposals."""
import copy
from q2_solver import SceneBGraph,owner_of
from q2_evaluator import key
from q2_physical import legal_positions
from q2_guarded import structural
from q2_bottleneck_j import analyze
from q3_solver import evaluate,audit,audit_cache

def witnesses(raw,plan,result,s,d):
    from multicore_cut_evaluate_problem_3 import _build_scene_b_tasks
    tasks,links,*_=_build_scene_b_tasks(raw,plan,s['bandwidth'],s['capacity'])
    diag=analyze(tasks,links,result,d,s['bandwidth'])
    critical={(x['core'],x['op']) for x in diag['critical_chain']}
    return extract(result,critical),diag['start_reconstruction_max_error']

def extract(result,critical):
    ops={(c['core_id'],o['op_id']):o for c in result['per_core_timeline'] for o in c['ops']}
    resident={};evicted={};out=[]
    for index,e in enumerate(result['cache_events']):
        tid=e['tensor_id'];op=ops[e['core_id'],e['op_id']]
        if e['event']=='insert':
            for victim in e['evicted_tensor_ids']:
                birth=resident.pop(victim)
                evicted[victim]=dict(fill_time=birth,eviction_time=e['time'],eviction_event=index,
                    evicting_tensor=tid,source_group=op['subgraph_id'],source_core=e['core_id'],source_op=e['op_id'])
            resident[tid]=e['time'];evicted.pop(tid,None)
        elif e['event']=='miss' and tid in evicted and (e['core_id'],e['op_id']) in critical:
            cause=evicted[tid]
            if cause['source_group'] is None or op['subgraph_id'] is None or cause['source_group']==op['subgraph_id']:continue
            out.append(dict(cause,tensor=tid,consumer_group=op['subgraph_id'],consumer_core=e['core_id'],consumer_op=e['op_id'],read_time=e['time'],miss_event=index,size=e['size_bytes'],duration=op['duration']))
    return sorted(out,key=lambda e:(-e['duration'],-e['size'],e['read_time'],e['consumer_op']))

def proposals(g,plan,result,events,mode,budget):
    owners=owner_of(plan);starts={}
    for c in result['per_core_timeline']:
        for o in c['ops']:
            group=o['subgraph_id']
            if group is not None:starts[group]=min(starts.get(group,float('inf')),o['start'])
    def moves(base,group,direction,target):
        core=owners[group];seqs,lo,hi=legal_positions(g,base,group,core)
        old=base['core_schedules'][core].index(group)
        positions=[i for i in range(lo,hi+1) if (i<old if direction<0 else i>old)]
        if not positions:return
        near=min(positions,key=lambda i:(abs((starts.get(seqs[core][i],result['makespan']) if i<len(seqs[core]) else result['makespan'])-target),i))
        for at in dict.fromkeys([max(positions) if direction<0 else min(positions),near,min(positions) if direction<0 else max(positions)]):
            p=dict(node_to_subgraph=dict(base['node_to_subgraph']),core_schedules=copy.deepcopy(seqs));p['core_schedules'][core].insert(at,group)
            structural(g,p);yield p,dict(group=group,core=core,old_position=old,new_position=at)
    def menu(e):
        u,v=e['consumer_group'],e['source_group']
        def both_changed(p):
            return p['core_schedules'][owners[u]].index(u)<plan['core_schedules'][owners[u]].index(u) and p['core_schedules'][owners[v]].index(v)>plan['core_schedules'][owners[v]].index(v)
        early=starts[u]+e['eviction_time']-e['read_time']-1
        late=starts[v]+e['read_time']-e['eviction_time']+1
        if mode=='consumer':
            for p,m in moves(plan,u,-1,early):yield dict(plan=p,move=dict(witness=e,changes=[m]))
        elif mode=='source':
            for p,m in moves(plan,v,1,late):yield dict(plan=p,move=dict(witness=e,changes=[m]))
        else:
            for a,m in moves(plan,u,-1,early):
                for p,n in moves(a,v,1,late):
                    if both_changed(p):yield dict(plan=p,move=dict(witness=e,changes=[m,n]))
            for a,m in moves(plan,v,1,late):
                for p,n in moves(a,u,-1,early):
                    if both_changed(p):yield dict(plan=p,move=dict(witness=e,changes=[m,n]))
    queues=[menu(e) for e in events[:32]];seen={key(plan)};out=[]
    while queues and len(out)<budget:
        remaining=[]
        for q in queues:
            for x in q:
                h=key(x['plan'])
                if h in seen:continue
                seen.add(h);out.append(x);remaining.append(q);break
            if len(out)==budget:break
        queues=remaining
    return out

def solve(raw,seed,s,d,c,mode,budget=24):
    anchor=evaluate(raw,seed,s,d,c);events,error=witnesses(raw,seed,anchor,s,d)
    g=SceneBGraph(raw,s,d);best=seed;result=anchor;rows=[]
    objective=lambda r:(r['makespan'],r['data_movement_bytes']['added_copy_bytes'])
    for x in proposals(g,seed,anchor,events,mode,budget):
        r=evaluate(raw,x['plan'],s,d,c);accepted=objective(r)<objective(result)
        # Tensor identity is stable; generated operation IDs need not be stable.
        e=x['move']['witness'];read_ops={(core['core_id'],o['op_id']):o for core in r['per_core_timeline'] for o in core['ops']}
        reads=[z for z in r['cache_events'] if z['event'] in ('hit','miss') and z['tensor_id']==e['tensor'] and read_ops[z['core_id'],z['op_id']]['subgraph_id']==e['consumer_group']]
        rows.append(dict(plan_sha256=key(x['plan']),move=x['move'],makespan=r['makespan'],added_bytes=objective(r)[1],accepted=accepted,target_group_reads=[dict(time=z['time'],event=z['event'],core=z['core_id']) for z in reads]))
        if accepted:best,result=x['plan'],r
    replay=evaluate(raw,best,s,d,c);assert replay==result
    return best,result,anchor,dict(mode=mode,budget=budget,evaluations=rows,rounds=[dict(witness_count=len(events),reconstruction_error=error)],replay_equal=True,checks=audit(raw,best,result,s,d))
