"""Reserve root coverage, then allocate to measured-gain proposal families."""
from q2_evaluator import key
from q2_solver import SceneBGraph
from q3_solver import evaluate, audit
from q3_asap_fast import proposals as asap
from q3_cache_search_fast import candidates as cache

def solve(raw,seed,s,d,c,mode,budget=24):
    g=SceneBGraph(raw,s,d);anchor=evaluate(raw,seed,s,d,c)
    best,result=seed,anchor;objective=lambda r:(r['makespan'],r['data_movement_bytes']['added_copy_bytes'])
    seen={key(seed)};evaluations=[];rounds=[];menus={};gains={'asap':0.,'cache':0.};calls={'asap':0,'cache':0}
    families=['asap'] if mode=='reserved' else ['asap','cache']
    def queue(base,r,f):
        h=key(base)
        if (h,f) not in menus:
            xs,diag=asap(g,base,r,s,d,budget) if f=='asap' else cache(g,base,r,'joint',budget,s,d)
            menus[h,f]=iter(xs);rounds.append(dict(seed=h,family=f,diagnostic=diag))
        return menus[h,f]
    def take(base,r,f,phase):
        nonlocal best,result
        for x in queue(base,r,f):
            h=key(x['plan'])
            if h in seen:continue
            seen.add(h);new=evaluate(raw,x['plan'],s,d,c)
            gain=max(0,(r['makespan']-new['makespan'])/anchor['makespan'])
            calls[f]+=1;gains[f]+=gain
            accepted=objective(new)<objective(result)
            evaluations.append(dict(plan_sha256=h,parent=key(base),family=f,phase=phase,move=x['move'],makespan=new['makespan'],added_bytes=objective(new)[1],gain_from_parent=gain,accepted=accepted))
            if accepted:best,result=x['plan'],new
            return True
        return False
    # Reserve the first 16 unique calls for the unchanged root; exhausted menus
    # release their quota. This is coverage, not a promise to exhaust 24 root moves.
    for i in range(min(16,budget)):
        order=families[i%len(families):]+families[:i%len(families)]
        if not any(take(seed,anchor,f,'root_reserve') for f in order):break
    while len(evaluations)<budget:
        i=len(evaluations)
        order=families[i%len(families):]+families[:i%len(families)]
        if mode=='adaptive' and i%4!=3:
            order=sorted(families,key=lambda f:(-gains[f]/max(1,calls[f]),families.index(f)))
        # Half remaining calls stay on root. Every fourth call explores the
        # other family; family scores are observations, not causal estimates.
        bases=[(seed,anchor),(best,result)] if i%2==0 else [(best,result),(seed,anchor)]
        success=False
        for base,r in bases:
            for f in order:
                if take(base,r,f,'allocate'):success=True;break
            if success:break
        if not success:break
    replay=evaluate(raw,best,s,d,c);assert replay==result and objective(result)<=objective(anchor)
    return best,result,anchor,dict(mode=mode,budget=budget,evaluations=evaluations,rounds=rounds,
        family_calls=calls,family_observed_gains=gains,replay_equal=True,checks=audit(raw,best,result,s,d))
