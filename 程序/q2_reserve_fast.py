"""r07 engineering-only reserve implementation; frozen r05/r06 untouched."""
import time
import q2_controlled as controlled
from q2_structural_route import REFERENCE
from q2_current import structure_candidates,stable
from q1_structural_seeds import GraphModel
from q2_reserve_gate import refill
from q2_evaluator import key


def menu(raw,settings,delay,n,migration,metadata):
    start=time.perf_counter()
    g,old=structure_candidates(raw,settings,delay,n)
    metadata['legacy_menu_seconds']=time.perf_counter()-start
    m=GraphModel(raw,settings,dict(task_cross_core_wait_cycles=delay,task_same_core_wait_cycles=0))
    if max(map(len,m.components))/len(m.ids)<=.5:
        metadata['admitted_old_candidates']=0
        metadata['candidate_seconds']=time.perf_counter()-start
        return g,old
    t=time.perf_counter();_,ref=REFERENCE(raw,settings,delay,n,False)
    metadata['reference_menu_seconds']=time.perf_counter()-t
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
    stats.update(arm='fast',**metadata)
    assert stats['slots']==12
    return plan,result,stats
