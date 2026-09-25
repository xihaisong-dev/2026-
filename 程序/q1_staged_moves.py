"""Structure-conditioned priors and bounded timeline-guided joint moves."""
import copy
from q1_timed_candidates import frontier_mapping,schedule

def profile(g,groups):
    work=sum(max(1,o['cycles']) for o in g.ops.values())
    chain={}
    for u in reversed(g.order):chain[u]=max(1,g.ops[u]['cycles'])+max((chain[v] for v in g.succ[u]),default=0)
    return dict(components=len(groups),largest_component_fraction=max(map(len,groups),default=0)/max(1,len(g.ops)),
        chain_work_fraction=max(chain.values(),default=0)/max(1,work),
        ddr_work_fraction=sum(t[0] for t in g.tensors)/g.bandwidth/max(1,work))

def weights(features,arms):
    w={a:1. for a in arms}
    if 'vector_packing' in w:w['vector_packing']+=2*(1-features['largest_component_fraction'])
    w['boundary']+=2*features['chain_work_fraction']
    w['list_order']+=min(2,features['ddr_work_fraction'])
    if 'timeline_joint' in w:w['timeline_joint']+=features['chain_work_fraction']+min(1,features['ddr_work_fraction'])
    return w

def timeline_move(g,plan,result,k,rng,index):
    mapping={int(u):s for u,s in plan['node_to_subgraph'].items()}
    groups,pred,succ,_=g.view(mapping)
    tasks={t['task_id']:t for c in result['per_core_timeline'] for t in c['tasks']}
    end=max(tasks,key=lambda s:tasks[s]['end']);path=[end]
    # Follow actual release blockers, including same-core serialization.
    previous={b:a for seq in plan['core_schedules'] for a,b in zip(seq,seq[1:])}
    while len(path)<12:
        s=path[-1];causes=set(pred[s])
        if s in previous:causes.add(previous[s])
        causes={p for p in causes if p not in path and tasks[p]['end']<=tasks[s]['start']}
        if not causes:break
        path.append(max(causes,key=lambda p:tasks[p]['end']))
    s=path[index%len(path)]
    if index%3==0 and pred[s]:
        p=max(pred[s],key=lambda p:tasks[p]['end'])
        mapping={u:p if t==s else t for u,t in mapping.items()}
        g.view(mapping)
        return schedule(g,mapping,k,rng,index%6)
    if index%3==1 and len(groups[s])>1:
        part=frontier_mapping(g,k,rng,index,nodes=groups[s],target_groups=2)
        new=max(groups)+1;mapping.update({u:new+t for u,t in part.items()})
        g.view(mapping)
        return schedule(g,mapping,k,rng,index%6)
    trial=copy.deepcopy(plan);source=next(c for c,seq in enumerate(trial['core_schedules']) if s in seq)
    trial['core_schedules'][source].remove(s)
    target=(source+1+index//3)%k;seq=trial['core_schedules'][target]
    position=sum(tasks[t]['end']<=tasks[s]['start'] for t in seq)
    seq.insert(position,s)
    return trial
