"""Controlled B placement and repair comparisons; r02 sources stay frozen."""
import copy,heapq,time
from collections import defaultdict
from q1_structural_seeds import GraphModel,_component_plan,_plan,_heft_plan
from q1_memory_routes import hybrid_pool
from q2_solver import SceneBGraph,context
from q2_current import EvaluationContext
from q2_evaluator import key,evaluate
from q2_bottleneck_j import diagnose,pool


def heft(m,g,groups,n,corrected=False):
    """Reference B HEFT; corrected arm changes cross-transfer estimates only.

    Rank, duration, ready order, core serialization and tie breaks are shared.
    Ordinary tensors are charged once per source/destination core, direct edges
    individually. Existing destination consumers imply an already planned copy.
    Carrier uses latest producer-group finish on its source core; this remains a
    heuristic release estimate, not a substitute for COPY-level B simulation.
    """
    mapping={u:s for s,nodes in enumerate(groups) for u in nodes}
    _,pd,sc,topo,incident,_,_=context(g,mapping)
    edge=defaultdict(int)
    for u in m.ids:
        for v in m.succ[u]:
            if mapping[u]!=mapping[v]:edge[mapping[u],mapping[v]]+=m.edge_bytes.get((u,v),0)
    vectors=[m.cost_vector(nodes) for nodes in groups]
    duration=[max(v.values())+.08*sum(v.values()) for v in vectors]
    rank={}
    for s in reversed(topo):rank[s]=duration[s]+max((rank[v] for v in sc[s]),default=0)
    degree={s:len(pd[s]) for s in pd};ready=[(-rank[s],s) for s in topo if not degree[s]];heapq.heapify(ready)
    owners={};finish={};core_time=[0.]*n;order=[]
    direct=defaultdict(list)
    for u,v,size in g.direct_edges:
        if mapping[u]!=mapping[v]:direct[mapping[v]].append((mapping[u],size))
    while ready:
        _,s=heapq.heappop(ready);options=[]
        for c in range(n):
            charged=defaultdict(float)
            if corrected:
                for tid in incident[s]:
                    size,_,ps,cs,_=g.tensors[tid]
                    if not any(mapping[v]==s for v in cs):continue
                    if any(mapping[v] in owners and owners[mapping[v]]==c for v in cs):continue
                    by_core=defaultdict(list)
                    for v in ps:
                        p=mapping[v]
                        if p in owners and owners[p]!=c:by_core[owners[p]].append(p)
                    for candidates in by_core.values():
                        p=max(candidates,key=lambda p:(finish[p],p));charged[p]+=2.*size/m.bandwidth
                for p,size in direct[s]:
                    if owners[p]!=c:charged[p]+=2.*size/m.bandwidth
            release=core_time[c];transfer=0.
            for p in sorted(pd[s]):
                cross=owners[p]!=c
                traffic=charged[p] if corrected else (2.*edge[p,s]/m.bandwidth if cross else 0.)
                release=max(release,finish[p]+(m.cross_wait if cross else 0.)+traffic)
                transfer+=traffic
            options.append((release+duration[s],transfer,core_time[c],c))
        done,_,_,c=min(options);owners[s]=c;finish[s]=done;core_time[c]=done;order.append(s)
        for v in sorted(sc[s]):
            degree[v]-=1
            if not degree[v]:heapq.heappush(ready,(-rank[v],v))
    return _plan(groups,owners,order,n)


def candidates(raw,settings,delay,n,corrected):
    m=GraphModel(raw,settings,dict(task_cross_core_wait_cycles=delay,task_same_core_wait_cycles=0));g=SceneBGraph(raw,settings,delay)
    common=[('components_pipe',_component_plan(m,n,'pipe',True)),('components_reuse',_component_plan(m,n,'pipe',False,'reuse'))]
    partitions=[]
    for name,p in hybrid_pool(m,n):
        groups=defaultdict(list)
        for u,s in p['node_to_subgraph'].items():groups[s].append(int(u))
        partitions.append((name,[sorted(groups[s]) for s in sorted(groups)]))
    partitions.extend([('chains',m.chain_groups()),('depth8',m.connected_groups({u:m.depth[u]//8 for u in m.ids}))])
    output=common+[(name,heft(m,g,groups,n,corrected)) for name,groups in partitions]
    while len(output)<6:output.append(('padding',copy.deepcopy(output[-1][1])))
    return g,output[:6]


def mixed_proposals(ordinary,guided,anchor):
    # Fixed slots, not deduplication backfill that could grant one arm extra moves.
    result=[]
    for label,items in [('ordinary',ordinary[:2]),('guided',guided[:2])]:
        for j in range(2):result.append(items[j] if j<len(items) else dict(plan=anchor,move={'padding':label}))
    return result


def solve(raw,settings,delay,provenance,n,migration,arm):
    start=time.perf_counter();ctx=EvaluationContext(raw,settings,delay,provenance);rows=[];best=result=None
    def assess(name,p):
        nonlocal best,result
        t=time.perf_counter();hits=ctx.hits
        try:
            r=ctx.evaluate(p)
            if result is None or (r['makespan'],r['data_movement_bytes']['added_copy_bytes'])<(result['makespan'],result['data_movement_bytes']['added_copy_bytes']):best,result=copy.deepcopy(p),r
            row=dict(status='ok',makespan=r['makespan'],bytes=r['data_movement_bytes']['added_copy_bytes'])
        except (ValueError,RuntimeError) as e:row=dict(status='invalid',error=str(e))
        row.update(name=name,plan_sha256=key(p),partition_sha256=__import__('q2_current').stable(p['node_to_subgraph']),seconds=time.perf_counter()-t,cache_hit=ctx.hits>hits);rows.append(row)
    whole=dict(node_to_subgraph={str(o['id']):0 for o in raw['ops'] if o['op'] not in {'COPY_IN','COPY_OUT'}},core_schedules=[[0]]+[[] for _ in range(n-1)])
    assess('migration_B',migration);assess('whole',whole)
    g,menu=candidates(raw,settings,delay,n,arm=='placement_corrected')
    for name,p in menu:assess(name,p)
    assert result is not None
    anchor=copy.deepcopy(best);base=result['makespan'];base_bytes=result['data_movement_bytes']['added_copy_bytes'];diagnostic_seconds=0.
    if arm.startswith('j_'):
        ordinary=pool(g,anchor,None,budget=4)
        guided=[]
        if arm!='j_ordinary':
            d=diagnose(raw,anchor,result,settings,delay);diagnostic_seconds=d['seconds'];guided=pool(g,anchor,d,budget=4)
        proposals=ordinary if arm=='j_ordinary' else guided if arm=='j_guided' else mixed_proposals(ordinary,guided,anchor)
        for j in range(4):
            item=proposals[j] if j<len(proposals) else dict(plan=anchor,move={'padding':True})
            assess('J:'+str(item['move']),item['plan'])
    seconds=time.perf_counter()-start;t=time.perf_counter();replay=evaluate(raw,best,settings,delay);assert replay==result
    return best,result,dict(arm=arm,base_makespan=base,base_bytes=base_bytes,base_plan_sha256=key(anchor),evaluations=rows,slots=len(rows),
        official_calls=ctx.calls,cache_hits=ctx.hits,solve_seconds=seconds,replay_seconds=time.perf_counter()-t,diagnostic_seconds=diagnostic_seconds,replay_equal=True)
