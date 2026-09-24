"""r08 shared graph preparation; same r07 candidates and decisions."""
import time,copy
from collections import defaultdict
from q1_memory_routes import hybrid_pool
from q1_structural_seeds import _component_plan
from q2_solver import SceneBGraph,place,order_plan
from q2_controlled import heft
import q2_controlled as controlled
from q2_structural_route import REFERENCE
from q2_current import structure_candidates,stable
from q1_structural_seeds import GraphModel
from q2_reserve_gate import refill
from q2_evaluator import key


def prepare(raw,settings,delay,n):
    m=GraphModel(raw,settings,dict(task_cross_core_wait_cycles=delay,task_same_core_wait_cycles=0))
    g=SceneBGraph(raw,settings,delay)
    common=[('components_pipe',_component_plan(m,n,'pipe',True)),('components_reuse',_component_plan(m,n,'pipe',False,'reuse'))]
    partitions=[(name,{int(u):sid for u,sid in p['node_to_subgraph'].items()}) for name,p in hybrid_pool(m,n)]
    partitions.extend((name,{u:i for i,group in enumerate(groups) for u in group}) for name,groups in [
        ('chains',m.chain_groups()),('depth8',m.connected_groups({u:m.depth[u]//8 for u in m.ids}))])
    old=list(common);ref=list(common);dominant=max(map(len,m.components))/len(m.ids)>.5
    for name,mapping in partitions:
        old.append((name,order_plan(g,mapping,place(g,mapping,n,True),n,False)))
        if dominant:
            groups=defaultdict(list)
            for u,sid in mapping.items():groups[sid].append(u)
            ref.append((name,heft(m,g,[sorted(groups[sid]) for sid in sorted(groups)],n,False)))
    while len(old)<6:old.append(('structure_padding',copy.deepcopy(old[-1][1])))
    if dominant:
        while len(ref)<6:ref.append(('padding',copy.deepcopy(ref[-1][1])))
    return m,g,old[:6],ref[:6],dominant


def menu(raw,settings,delay,n,migration,metadata):
    start=time.perf_counter()
    m,g,old,ref,dominant=prepare(raw,settings,delay,n)
    metadata['shared_menu_seconds']=time.perf_counter()-start
    if not dominant:
        metadata['admitted_old_candidates']=0
        metadata['candidate_seconds']=time.perf_counter()-start
        return g,old
    metadata['shared_preparation']=True
    assert [stable(p['node_to_subgraph']) for _,p in old]==[stable(p['node_to_subgraph']) for _,p in ref]
    routed=old[:4]+[(name+'_reference_gate',p) for name,p in ref[4:]]
    whole=dict(node_to_subgraph={str(o['id']):0 for o in raw['ops'] if o['op'] not in {'COPY_IN','COPY_OUT'}},core_schedules=[[0]]+[[] for _ in range(n-1)])
    prefix=[('migration',migration),('whole',whole)]
    original,count=refill(prefix,routed,[(name+'_reserve',p) for name,p in old[4:6]],lambda x:key(x[1]))
    output=original
    if count:
        # Keep the unused duplicate occurrences where they originally appeared.
        # Remove only the last count duplicates; append admitted plans after all
        # original first occurrences. Thus first-occurrence/tie priority is exact.
        seen={key(p) for _,p in prefix};duplicates=[]
        for j,(_,p) in enumerate(routed):
            h=key(p)
            if h in seen:duplicates.append(j)
            seen.add(h)
        removed=set(duplicates[-count:])
        extras=[x for x in original if x[0].endswith('_reserve')]
        output=[x for j,x in enumerate(routed) if j not in removed]+extras
        def first(items):
            seen={key(p) for _,p in prefix};out=[]
            for _,p in items:
                h=key(p)
                if h not in seen:out.append(h);seen.add(h)
            return out
        assert first(output)==first(original) and len(output)==6
    metadata.update(admitted_old_candidates=count,candidate_seconds=time.perf_counter()-start)
    return g,output


def solve(raw,settings,delay,provenance,n,migration):
    original=controlled.candidates;original_pool=controlled.pool;metadata={}
    def proposals(*args,**kwargs):
        t=time.perf_counter();result=original_pool(*args,**kwargs)
        metadata['j_generation_seconds']=time.perf_counter()-t
        return result
    try:
        controlled.candidates=lambda raw,settings,delay,n,corrected:menu(raw,settings,delay,n,migration,metadata)
        controlled.pool=proposals
        plan,result,stats=controlled.solve(raw,settings,delay,provenance,n,migration,'j_ordinary')
    finally:
        controlled.candidates=original;controlled.pool=original_pool
    stats.update(arm='shared',**metadata)
    assert stats['slots']==12
    return plan,result,stats
