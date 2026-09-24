"""Observed-time critical graph / FIFO head-of-line diagnostics and bounded J.

Observed durations include DDR contention. The critical graph explains a fixed
run, not counterfactual savings. HOL intervals are opportunities, not guarantees.
"""
from collections import defaultdict
import copy
import time
from q1_solver import topological
from q2_solver import context, owner_of
from q2_physical import legal_positions
from q2_guarded import structural
from q2_evaluator import key


def analyze(tasks, links, result, delay, bandwidth):
    from schedule_step3 import _op_duration, _uses_ddr_bandwidth
    entries={(t['core_id'],o['op_id']):o for t in result['per_core_timeline'] for o in t['ops']}
    pred={v:{} for v in entries}
    nonfifo={v:{} for v in entries}
    def add(v,u,lag,kind):
        if u not in pred[v] or lag>pred[v][u][0]:pred[v][u]=(lag,kind)
    for c,t in tasks.items():
        for o in t['op_by_id']:
            v=(c,o)
            for p in t['op_preds'][o]:
                add(v,(c,p),0,'data_or_memory');nonfifo[v][c,p]=0
        for pipe,seq in t['pipe_ops'].items():
            for a,b in zip(seq,seq[1:]):add((c,b),(c,a),0,'fifo')
    for link in links:
        u=(link['source_core'],link['source_copy_out_id']);v=(link['target_core'],link['target_copy_in_id'])
        add(v,u,delay,'cross_copy');nonfifo[v][u]=delay
    succ={v:set() for v in pred}
    for v,ps in pred.items():
        for u in ps:succ[u].add(v)
    order=topological({v:set(p) for v,p in pred.items()},succ)
    earliest={};end={};parent={};max_residual=0
    for v in order:
        candidates=[(end[u]+lag,u,kind,lag) for u,(lag,kind) in pred[v].items()]
        best=max(candidates,default=(0,None,'origin',0))
        earliest[v]=best[0];end[v]=best[0]+entries[v]['duration'];parent[v]=best[1:]
        max_residual=max(max_residual,abs(earliest[v]-entries[v]['start']))
    assert max_residual==0, ('Unexplained start time',max_residual)
    makespan=max(end.values(),default=0)
    assert makespan==result['makespan']
    suffix={}
    for v in reversed(order):suffix[v]=max((pred[w][v][0]+entries[w]['duration']+suffix[w] for w in succ[v]),default=0)
    critical={v for v in order if end[v]+suffix[v]==makespan}
    group_score=defaultdict(float)
    for v in critical:
        s=entries[v]['subgraph_id']
        if s is not None:group_score[s]+=entries[v]['duration']
    terminal=max(order,key=lambda v:(end[v],v)) if order else None
    chain=[];v=terminal
    while v is not None:
        p,kind,lag=parent[v]
        chain.append(dict(core=v[0],op=v[1],group=entries[v]['subgraph_id'],start=earliest[v],end=end[v],incoming_kind=kind,incoming_lag=lag))
        v=p
    chain.reverse()
    hol=[]
    ready={v:max((entries[u]['end']+lag for u,lag in ps.items()),default=0) for v,ps in nonfifo.items()}
    for c,t in tasks.items():
        for pipe,seq in t['pipe_ops'].items():
            for i,o in enumerate(seq):
                v=(c,o);previous=entries[c,seq[i-1]]['end'] if i else 0
                stop=entries[v]['start']
                if stop<=previous:continue
                blocked=[]
                # Bounded opportunity scan; observed upstream readiness includes memory dependencies.
                for q in seq[i+1:i+17]:
                    w=(c,q);begin=max(previous,ready[w])
                    if begin<stop:
                        blocked.append(dict(op=q,group=entries[w]['subgraph_id'],ready=ready[w],opportunity=stop-begin))
                if not blocked:continue
                gap=max(x['opportunity'] for x in blocked)  # union of nested intervals, never sum duplicates
                tight=[u for u,lag in nonfifo[v].items() if entries[u]['end']+lag==ready[v]]
                groups={entries[v]['subgraph_id']}|{x['group'] for x in blocked}|{entries[u]['subgraph_id'] for u in tight}
                for s in groups:
                    if s is not None:group_score[s]+=gap*(2 if v in critical else 1)
                hol.append(dict(core=c,pipe=pipe,head_op=o,head_group=entries[v]['subgraph_id'],idle_start=previous,idle_end=stop,
                                opportunity_cycles=gap,on_critical_graph=v in critical,blocked=blocked,
                                releasing_groups=sorted({entries[u]['subgraph_id'] for u in tight if entries[u]['subgraph_id'] is not None})))
    ddr=[]
    for v,o in entries.items():
        t=tasks[v[0]];op=t['op_by_id'][v[1]]
        if _uses_ddr_bandwidth(op,t['in_tids'],t['out_tids'],t['tensor_by_id']):
            base=_op_duration(op,t['in_tids'],t['out_tids'],t['tensor_by_id'],bandwidth)
            ddr.append(dict(core=v[0],op=v[1],base_duration=base,observed_duration=o['duration'],extra=o['duration']-base))
    return dict(makespan=makespan,start_reconstruction_max_error=max_residual,critical_ops=len(critical),
                critical_chain=chain,group_priority=sorted(group_score,key=lambda s:(-group_score[s],s)),
                group_scores=dict(group_score),hol=sorted(hol,key=lambda x:(-x['opportunity_cycles'],x['core'],x['head_op'])),
                ddr_observed_extra_cycles=sum(x['extra'] for x in ddr),ddr=ddr,
                caveat='Fixed-run explanation; DDR extra overlaps across transfers and is not additive makespan loss; HOL is observed readiness opportunity.')


def diagnose(raw,plan,result,settings,delay):
    from multicore_cut_evaluate_problem_2 import _build_scene_b_tasks
    start=time.perf_counter()
    tasks,links,_,traffic,_=_build_scene_b_tasks(raw,plan,settings['bandwidth'],settings['capacity'])
    assert traffic==result['data_movement_bytes']
    d=analyze(tasks,links,result,delay,settings['bandwidth'])
    d['seconds']=time.perf_counter()-start
    return d


def pool(g,plan,diagnostic=None,budget=8):
    """Same legal move menu; only group/core/insertion priority uses diagnostics.
    One proposal per prioritized group per round prevents one group consuming all slots.
    """
    owners=owner_of(plan);mapping={int(u):s for u,s in plan['node_to_subgraph'].items()}
    groups,_,_,_,incident,_,ranks=context(g,mapping)
    ordinary=sorted(groups,key=lambda s:(-(ranks[s]+sum(g.tensors[i][0] for i in incident[s])/g.bandwidth),s))
    priority=list(dict.fromkeys(([s for s in diagnostic['group_priority'] if s in groups] if diagnostic else [])+ordinary))[:32]
    queues=[]
    for s in priority:
        moves=[]
        cores=list(range(len(plan['core_schedules'])))
        if diagnostic:
            target=[]
            for h in diagnostic['hol']:
                if s in h['releasing_groups']:target.append(h['core'])
            cores=list(dict.fromkeys(target+cores))
        for c in cores:
            seqs,lo,hi=legal_positions(g,plan,s,c)
            if lo>hi:continue
            for at in list(dict.fromkeys([lo,hi,(lo+hi)//2])):
                trial={'node_to_subgraph':dict(plan['node_to_subgraph']),'core_schedules':copy.deepcopy(seqs)}
                trial['core_schedules'][c].insert(at,s)
                if key(trial)==key(plan):continue
                structural(g,trial)
                moves.append(dict(plan=trial,move=dict(group=s,source=owners[s],destination=c,position=at,legal_interval=[lo,hi])))
        if moves:queues.append(moves)
    result=[];seen={key(plan)}
    while queues and len(result)<budget:
        remaining=[]
        for q in queues:
            while q:
                item=q.pop(0);h=key(item['plan'])
                if h not in seen:seen.add(h);result.append(item);break
            if q:remaining.append(q)
            if len(result)==budget:break
        queues=remaining
    return result
