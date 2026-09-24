"""Lazy, order-equivalent Q2 neighborhood enumeration; no scoring approximation."""
import copy
from q2_solver import context,owner_of
from q2_evaluator import key
from q2_guarded import structural


def pool(g,plan,diagnostic=None,budget=8):
    if budget<=0:return []
    owners=owner_of(plan);mapping={int(u):s for u,s in plan['node_to_subgraph'].items()}
    groups,pred0,succ0,_,incident,_,ranks=context(g,mapping)
    ordinary=sorted(groups,key=lambda s:(-(ranks[s]+sum(g.tensors[i][0] for i in incident[s])/g.bandwidth),s))
    priority=list(dict.fromkeys(([s for s in diagnostic['group_priority'] if s in groups] if diagnostic else [])+ordinary))[:32]
    original_key=key(plan)
    def moves(s):
        seqs=[[v for v in q if v!=s] for q in plan['core_schedules']]
        pred={v:set(x) for v,x in pred0.items()};succ={v:set(x) for v,x in succ0.items()}
        for q in seqs:
            for a,b in zip(q,q[1:]):pred[b].add(a);succ[a].add(b)
        def reach(edges):
            seen=set();todo=list(edges[s])
            while todo:
                v=todo.pop()
                if v==s:raise ValueError('Base order cycle')
                if v not in seen:seen.add(v);todo.extend(edges[v])
            return seen
        ancestors,descendants=reach(pred),reach(succ)
        cores=list(range(len(seqs)))
        if diagnostic:
            targets=[h['core'] for h in diagnostic['hol'] if s in h['releasing_groups']]
            cores=list(dict.fromkeys(targets+cores))
        for c in cores:
            q=seqs[c];lo=max((i+1 for i,v in enumerate(q) if v in ancestors),default=0)
            hi=min((i for i,v in enumerate(q) if v in descendants),default=len(q))
            if lo>hi:continue
            for at in dict.fromkeys([lo,hi,(lo+hi)//2]):
                trial=dict(node_to_subgraph=dict(plan['node_to_subgraph']),core_schedules=copy.deepcopy(seqs))
                trial['core_schedules'][c].insert(at,s)
                if key(trial)==original_key:continue
                yield dict(plan=trial,move=dict(group=s,source=owners[s],destination=c,position=at,legal_interval=[lo,hi]))
    queues=[moves(s) for s in priority];seen={original_key};result=[]
    while queues and len(result)<budget:
        remaining=[]
        for queue in queues:
            for item in queue:
                h=key(item['plan'])
                if h in seen:continue
                structural(g,item['plan']);seen.add(h);result.append(item);remaining.append(queue);break
            if len(result)==budget:break
        queues=remaining
    return result
