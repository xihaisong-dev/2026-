"""Observed bottleneck classification with accepted-batch re-diagnosis."""
from collections import Counter
from q2_evaluator import key
from q2_solver import SceneBGraph
from q3_solver import evaluate,audit
from q3_cache_search_fast import trace,candidates as cache_candidates
from q3_explore import candidates as old_candidates
from q3_neighborhood import pool

def classify(result,diagnostic):
    ops={(c['core_id'],o['op_id']):o for c in result['per_core_timeline'] for o in c['ops']}
    durations=Counter()
    for x in diagnostic['critical_chain']:
        o=ops[x['core'],x['op']]
        kind={'DDR':'ddr','CACHE_READ':'cache'}.get(o.get('memory_path'),'compute')
        durations[kind]+=x['end']-x['start'];durations['sync']+=x['incoming_lag']
    assert sum(durations.values())==result['makespan']
    label=max(['compute','ddr','cache','sync'],key=lambda k:durations[k])
    # Dominance is an observed chain share, not a proven causal bottleneck.
    return dict(label=label,cycles=dict(durations),shares={k:v/result['makespan'] for k,v in durations.items()})

def proposals(g,plan,result,s,d,budget,unclassified=False):
    diagnostic=trace(g.raw,plan,result,s,d);classification=classify(result,diagnostic)
    label=classification['label']
    order=['joint','window','split','ordinary'] if unclassified else {
        'compute':['split','joint','ordinary','window'],
        'ddr':['joint','window','ordinary','split'],
        'cache':['window','ordinary','joint','split'],
        'sync':['ordinary','joint','split','window']}[label]
    menus={}
    for f in order:
        if f in ['joint','window']:menus[f]=cache_candidates(g,plan,result,f,budget,s,d,traced=diagnostic)[0]
        elif f=='split':menus[f]=old_candidates(g,plan,result,'split',budget)
        else:menus[f]=pool(g,plan,dict(group_priority=list(dict.fromkeys(x['group'] for x in diagnostic['critical_chain'] if x['group'] is not None)),hol=[]),budget=budget)
    # Weighted deterministic interleave; all families remain represented.
    cycle=order if unclassified else [order[0],order[0],order[1],order[2],order[3]]
    offsets={f:0 for f in order};seen={key(plan)};out=[]
    while len(out)<budget:
        progressed=False
        for f in cycle:
            while offsets[f]<len(menus[f]):
                item=menus[f][offsets[f]];offsets[f]+=1;h=key(item['plan']);progressed=True
                if h not in seen:
                    seen.add(h);out.append(dict(plan=item['plan'],move=item['move'],family=f));break
            if len(out)>=budget:break
        if not progressed:break
    return out,classification

def solve(raw,seed,s,d,c,mode,budget=24):
    anchor=evaluate(raw,seed,s,d,c);best=seed;result=anchor;g=SceneBGraph(raw,s,d)
    seen={key(seed)};evaluations=[];rounds=[]
    objective=lambda r:(r['makespan'],r['data_movement_bytes']['added_copy_bytes'])
    while len(evaluations)<budget:
        base=best;base_result=result;menu,diagnostic=proposals(g,base,base_result,s,d,budget,mode=='unclassified_iterative')
        candidates=[x for x in menu if key(x['plan']) not in seen]
        record=dict(seed=key(base),before=base_result['makespan'],classification=diagnostic,accepted=False,calls=0)
        rounds.append(record)
        if not candidates:record['stop']='no_unseen_candidates';break
        accepted=False
        for i,x in enumerate(candidates):
            h=key(x['plan']);seen.add(h)
            try:
                r=evaluate(raw,x['plan'],s,d,c);improves=objective(r)<objective(result)
                if improves:best,result=x['plan'],r;accepted=True
                evaluations.append(dict(plan_sha256=h,round=len(rounds),family=x['family'],move=x['move'],makespan=r['makespan'],added_bytes=objective(r)[1],accepted=improves))
            except (ValueError,RuntimeError) as exc:evaluations.append(dict(plan_sha256=h,round=len(rounds),error=str(exc)))
            record['calls']+=1
            if len(evaluations)>=budget:break
            if mode!='single' and accepted and (i+1)%4==0:break
        record.update(after=result['makespan'],accepted=accepted,selected=key(best))
        if mode=='single' or not accepted:break
    replay=evaluate(raw,best,s,d,c);assert replay==result
    checks=audit(raw,best,replay,s,d)
    return best,replay,anchor,dict(mode=mode,budget=budget,evaluations=evaluations,rounds=rounds,replay_equal=True,checks=checks)
