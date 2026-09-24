"""Fixed structural gate; preserve first six baseline opportunities and ordinary J."""
import q2_controlled as controlled
from q2_current import structure_candidates,stable
from q1_structural_seeds import GraphModel

REFERENCE=controlled.candidates


def menu(raw,settings,delay,n,arm):
    if arm=='reference':return REFERENCE(raw,settings,delay,n,False)
    g,old=structure_candidates(raw,settings,delay,n)
    if arm=='legacy':return g,old
    assert arm=='routed'
    m=GraphModel(raw,settings,dict(task_cross_core_wait_cycles=delay,task_same_core_wait_cycles=0))
    dominant=max(map(len,m.components))/len(m.ids)>.5
    if not dominant:return g,old
    _,ref=REFERENCE(raw,settings,delay,n,False)
    assert [stable(p['node_to_subgraph']) for _,p in old]==[stable(p['node_to_subgraph']) for _,p in ref]
    # Migration, whole, components and first two structural opportunities stay.
    # Only the last two positions may change, irrespective of observed scores.
    return g,old[:4]+[(name+'_reference_gate',p) for name,p in ref[4:]]


def solve(raw,settings,delay,provenance,n,migration,arm):
    # Explicit, scoped dependency substitution; case workers use separate processes.
    original=controlled.candidates
    try:
        controlled.candidates=lambda raw,settings,delay,n,corrected:menu(raw,settings,delay,n,arm)
        plan,result,stats=controlled.solve(raw,settings,delay,provenance,n,migration,'j_ordinary')
    finally:controlled.candidates=original
    stats['arm']=arm
    return plan,result,stats
