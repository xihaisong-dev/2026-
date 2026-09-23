"""Fixed-pass dependency proxy: no official global event evaluation.

Retains prepared operation/memory dependencies and four Pipe orders. Only COPY
durations are updated using overlap from the previous pass; dependent operations
move via longest paths. Three relaxed passes do not solve exact bandwidth sharing.
"""
from bisect import bisect_right
from collections import defaultdict
from q1_solver import topological


def replay_network(order, pred, base, ddr, passes=3):
    durations = dict(base)
    def forward():
        start, end = {}, {}
        for v in order:
            start[v] = max((end[u]+delay for u,delay in pred[v].items()),default=0.)
            end[v] = start[v]+durations[v]
        return start,end
    for _ in range(passes):
        start,end = forward()
        events=defaultdict(int)
        for v in ddr:
            events[start[v]]+=1;events[end[v]]-=1
        points=sorted(events)
        if len(points)<2:break
        integral=[0.];active=0;rates=[]
        for a,b in zip(points,points[1:]):
            active+=events[a]
            rate=1/max(1,active)
            rates.append(rate);integral.append(integral[-1]+(b-a)*rate)
        def area(t):
            i=min(len(points)-2,max(0,bisect_right(points,t)-1))
            return integral[i]+(t-points[i])*rates[i]
        for v in ddr:
            mean_share=(area(end[v])-area(start[v]))/max(1e-9,end[v]-start[v])
            target=base[v]/max(mean_share,1e-9)
            durations[v]=.5*durations[v]+.5*target
    start,end=forward()
    return max(end.values(),default=0.), {'nodes':len(order),'ddr_ops':len(ddr),
        'passes':passes,'approximation':'fixed-pass overlap; not exact global simulation'}


def event_time(g,plan,tasks,passes=3):
    from schedule_step3 import _op_duration,_uses_ddr_bandwidth
    mapping={int(u):s for u,s in plan['node_to_subgraph'].items()}
    groups,task_pred,task_succ,_=g.view(mapping)
    owner={s:c for c,seq in enumerate(plan['core_schedules']) for s in seq}
    task_delay={(a,b):g.cross if owner[a]!=owner[b] else 0 for b in groups for a in task_pred[b]}
    for seq in plan['core_schedules']:
        for a,b in zip(seq,seq[1:]):
            task_pred[b].add(a);task_succ[a].add(b)
            task_delay[a,b]=max(task_delay.get((a,b),0),g.same)
    order=[];pred={};base={};ddr=set()
    for s in topological(task_pred,task_succ):
        task=tasks[s];begin=(s,'start');finish=(s,'end')
        pred[begin]={(a,'end'):task_delay[a,s] for a in task_pred[s]};base[begin]=0.;order.append(begin)
        op_pred={u:set(p) for u,p in task['op_preds'].items()}
        for seq in task['pipe_ops'].values():
            for a,b in zip(seq,seq[1:]):op_pred[b].add(a)
        op_succ={u:set() for u in op_pred}
        for u,ps in op_pred.items():
            for p in ps:op_succ[p].add(u)
        for u in topological(op_pred,op_succ):
            v=(s,u);op=task['op_by_id'][u]
            pred[v]={(s,p):0. for p in op_pred[u]};pred[v][begin]=0.
            base[v]=_op_duration(op,task['in_tids'],task['out_tids'],task['tensor_by_id'],g.bandwidth)
            if _uses_ddr_bandwidth(op,task['in_tids'],task['out_tids'],task['tensor_by_id']):ddr.add(v)
            order.append(v)
        pred[finish]={(s,u):0. for u in op_pred};base[finish]=0.;order.append(finish)
    return replay_network(order,pred,base,ddr,passes)
