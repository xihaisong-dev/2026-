"""Actual critical-chain diagnosis and at most twelve joint repair probes."""
import copy
from q1_solver import topological,validate
from q1_partition import repair


def critical_chain(g,plan,result):
    mapping={int(u):s for u,s in plan['node_to_subgraph'].items()}
    groups,pred,succ,_=g.view(mapping)
    owner={s:c for c,seq in enumerate(plan['core_schedules']) for s in seq}
    delay={(a,b):g.cross if owner[a]!=owner[b] else 0 for b in groups for a in pred[b]}
    for seq in plan['core_schedules']:
        for a,b in zip(seq,seq[1:]):
            pred[b].add(a);succ[a].add(b);delay[a,b]=max(delay.get((a,b),0),g.same)
    tasks={t['task_id']:t for c in result['per_core_timeline'] for t in c['tasks']}
    end={};parent={}
    for s in topological(pred,succ):
        a=max(pred[s],key=lambda a:(end[a]+delay[a,s],-a)) if pred[s] else None
        end[s]=tasks[s]['duration']+(end[a]+delay[a,s] if a is not None else 0)
        parent[s]=a
    chain=[];s=max(end,key=lambda s:(end[s],-s))
    while s is not None:chain.append(s);s=parent[s]
    chain.reverse()
    wait=sum(delay[a,b] for a,b in zip(chain,chain[1:]))
    return chain,delay,{'chain':chain,'wait_cycles':wait,'profile_path':max(end.values()),
                       'wait_fraction':wait/max(1,result['makespan'])}


def relocate(g,plan,task,target):
    trial=copy.deepcopy(plan)
    for seq in trial['core_schedules']:
        if task in seq:seq.remove(task)
    mapping={int(u):s for u,s in trial['node_to_subgraph'].items()}
    _,pred,succ,_=g.view(mapping)
    # All other core sequences remain hard constraints.
    for seq in trial['core_schedules']:
        for a,b in zip(seq,seq[1:]):pred[b].add(a);succ[a].add(b)
    rank={s:i for i,s in enumerate(topological(pred,succ))}
    seq=trial['core_schedules'][target]
    at=next((i for i,s in enumerate(seq) if rank[s]>rank[task]),len(seq))
    seq.insert(at,task);validate(g,trial)
    return trial


def candidates(g,plan,result,cores):
    chain,delay,info=critical_chain(g,plan,result)
    info.update(probes=0,valid=0,enabled=info['wait_fraction']>=.1)
    g.chain_stats.append(info)
    if not info['enabled']:return
    mapping={int(u):s for u,s in plan['node_to_subgraph'].items()};groups=g.view(mapping)[0]
    owner={s:c for c,seq in enumerate(plan['core_schedules']) for s in seq}
    seeds=sorted(range(len(chain)-1),key=lambda i:(-delay[chain[i],chain[i+1]],i))[:2]
    for i in seeds:
        if info['probes']>=12:return
        # One co-location without changing boundaries.
        a,b=chain[i:i+2];info['probes']+=1
        try:
            trial=relocate(g,plan,b,owner[a]);info['valid']+=1
            yield f'colocate_{a}_{b}',trial
        except (ValueError,RuntimeError):pass
        for width in [2,3]:
            if info['probes']>=12:return
            window=chain[i:i+width]
            if len(window)!=width or sum(len(groups[s]) for s in window)>512:continue
            merged={u:a if s in window else s for u,s in mapping.items()}
            info['probes']+=1
            try:
                trial=repair(g,plan,merged);info['valid']+=1
                yield f'merge_{a}_{width}',trial
            except (ValueError,RuntimeError):continue
            targets=list(dict.fromkeys([owner[window[-1]],
                 min(range(cores),key=lambda c:(sum(t['duration'] for t in result['per_core_timeline'][c]['tasks']),c))]))[:2]
            for c in targets:
                if info['probes']>=12:return
                info['probes']+=1
                try:
                    moved=relocate(g,trial,a,c);info['valid']+=1
                    yield f'merge_move_{a}_{width}_{c}',moved
                except (ValueError,RuntimeError):pass
