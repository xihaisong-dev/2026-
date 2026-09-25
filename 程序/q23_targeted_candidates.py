"""Bounded critical-wait repair and fixed-owner FIFO reuse ordering."""
import copy,random
from collections import Counter
from q2_solver import SceneBGraph,context,owner_of,order_plan,DEFAULTS
from q2_guarded import structural
from q2_physical import legal_positions
from q2_evaluator import key
from q2_timed_portfolio import generate
from q1_structural_seeds import GraphModel

def unique(items,seed,limit):
    out=[];seen={key(seed)}
    for p,label in items:
        h=key(p)
        if h in seen:continue
        seen.add(h);out.append((p,label))
        if len(out)>=limit:break
    return out

def ordinary(raw,seed,s,d,limit=16):
    g=SceneBGraph(raw,s,d);m=GraphModel(raw,s,dict(task_cross_core_wait_cycles=d,task_same_core_wait_cycles=0));rng=random.Random(0)
    def items():
        for i in range(48):
            try:yield generate('joint',m,g,seed,5,rng,i),'ordinary_joint'
            except (ValueError,RuntimeError):continue
    return unique(items(),seed,limit)

def waiting(raw,seed,result,s,d,limit=8):
    from q2_bottleneck_j import diagnose,pool
    diag=diagnose(raw,seed,result,s,d);g=SceneBGraph(raw,s,d)
    mapping={int(u):v for u,v in seed['node_to_subgraph'].items()};owners=owner_of(seed)
    priority=diag['group_priority'][:8];rank={v:i for i,v in enumerate(priority)}
    edges=sorted([(u,v) for u in g.order for v in sorted(g.succ[u]) if mapping[u]!=mapping[v] and (mapping[u] in rank or mapping[v] in rank)],key=lambda e:(min(rank.get(mapping[e[0]],99),rank.get(mapping[e[1]],99)),g.pos[e[1]],g.pos[e[0]]))[:8]
    def items():
        moves=iter(pool(g,seed,diag,budget=limit))
        for u,v in edges:
            x=next(moves,None)
            if x:yield x['plan'],'critical_wait_move'
            m=dict(mapping);m[u]=m[v];valid=set(m.values());o={a:b for a,b in owners.items() if a in valid}
            # Move a critical boundary op and place the destination group with
            # its producer; legal reordering repairs the quotient DAG.
            o[m[v]]=owners[mapping[u]]
            try:
                p=order_plan(g,m,o,5,True);structural(g,p);yield p,'critical_boundary_core_order'
            except (ValueError,RuntimeError):continue
        for x in moves:yield x['plan'],'critical_wait_move'
    return unique(items(),seed,limit),dict(critical_groups=priority,reconstruction_error=diag['start_reconstruction_max_error'])

def cache_order(raw,seed,result,s,d,guided,limit=16):
    g=SceneBGraph(raw,s,d);owners=owner_of(seed);priority=sorted(owners);diagnostic={}
    events=[]
    if guided:
        from multicore_cut_evaluate_problem_3 import _build_scene_b_tasks
        from q2_bottleneck_j import analyze
        from q3_eviction import extract
        tasks,links,*_=_build_scene_b_tasks(raw,seed,s['bandwidth'],s['capacity'])
        diag=analyze(tasks,links,result,d,s['bandwidth']);critical={(x['core'],x['op']) for x in diag['critical_chain']}
        events=extract(result,critical)
        ops={(c['core_id'],o['op_id']):o for c in result['per_core_timeline'] for o in c['ops']}
        counts=Counter(e['tensor_id'] for e in result['cache_events'] if e['event']=='miss');scores=Counter()
        for e in result['cache_events']:
            loc=e['core_id'],e['op_id'];group=ops[loc]['subgraph_id']
            if e['event']=='miss' and counts[e['tensor_id']]>1 and loc in critical and group is not None:
                scores[group]+=ops[loc]['duration']
        priority=sorted(scores,key=lambda x:(-scores[x],x))
        diagnostic=dict(critical_repeated_miss_groups=priority,eviction_witnesses=len(events),reconstruction_error=diag['start_reconstruction_max_error'])
    def items():
        if guided and events:
            from q3_eviction import proposals
            # Explicit bounded consumer and interference ordering, no migration.
            for mode in ['consumer','source']:
                for x in proposals(g,seed,result,events,mode,4):yield x['plan'],'cache_'+mode
        for group in priority[:12]:
            core=owners[group];seqs,lo,hi=legal_positions(g,seed,group,core);old=seed['core_schedules'][core].index(group)
            for at in dict.fromkeys([max(lo,old-1),lo,min(hi,old+1),hi]):
                if not lo<=at<=hi or at==old:continue
                p=dict(node_to_subgraph=dict(seed['node_to_subgraph']),core_schedules=copy.deepcopy(seqs));p['core_schedules'][core].insert(at,group)
                structural(g,p);assert owner_of(p)==owners and p['node_to_subgraph']==seed['node_to_subgraph']
                yield p,'critical_cache_order' if guided else 'ordinary_fixed_order'
    return unique(items(),seed,limit),diagnostic
