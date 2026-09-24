"""Retain distinct routed candidates; refill only duplicate menu opportunities."""
import q2_controlled as controlled
from q2_structural_route import menu as routed_menu
from q2_current import structure_candidates
from q2_evaluator import key


def refill(prefix,menu,extras,identity):
    seen={identity(p) for p in prefix};unique=[];duplicates=[]
    for item in menu:
        h=identity(item)
        if h in seen:duplicates.append(item)
        else:seen.add(h);unique.append(item)
    admitted=[]
    for item in extras:
        h=identity(item)
        if h not in seen and len(admitted)<len(duplicates):
            admitted.append(item);seen.add(h)
    if not admitted:return menu,0
    output=unique+admitted+duplicates[:len(duplicates)-len(admitted)]
    assert len(output)==len(menu)
    assert {identity(p) for p in menu}<={identity(p) for p in output}|{identity(p) for p in prefix}
    return output,len(admitted)


def solve(raw,settings,delay,provenance,n,migration):
    original=controlled.candidates;metadata={}
    whole=dict(node_to_subgraph={str(o['id']):0 for o in raw['ops'] if o['op'] not in {'COPY_IN','COPY_OUT'}},core_schedules=[[0]]+[[] for _ in range(n-1)])
    def candidates(raw,settings,delay,n,corrected):
        g,menu=routed_menu(raw,settings,delay,n,'routed')
        if not any(name.endswith('_reference_gate') for name,_ in menu):
            metadata['admitted_old_candidates']=0;return g,menu
        # Only existing duplicate opportunities may be reclaimed; no useful
        # routed candidate is removed and their tie priority remains unchanged.
        _,old=structure_candidates(raw,settings,delay,n)
        output,count=refill([('migration',migration),('whole',whole)],menu,
                           [(name+'_reserve',p) for name,p in old[4:6]],lambda x:key(x[1]))
        metadata['admitted_old_candidates']=count
        metadata['protected_routed_hashes']=[key(p) for _,p in menu]
        return g,output
    try:
        controlled.candidates=candidates
        plan,result,stats=controlled.solve(raw,settings,delay,provenance,n,migration,'j_ordinary')
    finally:controlled.candidates=original
    assert stats['slots']==12
    stats.update(arm='reserve',**metadata)
    assert set(metadata.get('protected_routed_hashes',[]))<={x['plan_sha256'] for x in stats['evaluations'][:8]}
    return plan,result,stats
