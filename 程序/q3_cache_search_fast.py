"""Critical-chain/FIFO-window proposal search. Official evaluator remains exact."""
import copy
from collections import Counter,defaultdict
from q2_solver import context,owner_of
from q2_evaluator import key
from q2_guarded import structural
from q2_physical import legal_positions
from q2_bottleneck_j import analyze
from q3_explore import candidates as old_candidates

def trace(raw,plan,result,settings,delay):
    from multicore_cut_evaluate_problem_3 import _build_scene_b_tasks
    tasks,links,*_=_build_scene_b_tasks(raw,plan,settings['bandwidth'],settings['capacity'])
    diagnostic=analyze(tasks,links,result,delay,settings['bandwidth'])
    critical={(x['core'],x['op']) for x in diagnostic['critical_chain']}
    ops={(c['core_id'],o['op_id']):o for c in result['per_core_timeline'] for o in c['ops']}
    windows=defaultdict(list);resident={};misses=[];users=defaultdict(Counter)
    for e in result['cache_events']:
        tid=e['tensor_id'];t=e['time']
        if e['event']=='insert':
            for v in e['evicted_tensor_ids']:
                begin=resident.pop(v);windows[v].append((begin,t))
            resident[tid]=t
        else:
            o=ops[e['core_id'],e['op_id']];s=o['subgraph_id']
            if s is None:continue
            users[tid][s]+=e['size_bytes']
            if e['event']=='miss':
                misses.append(dict(tensor=tid,group=s,core=e['core_id'],time=t,duration=o['duration'],size=e['size_bytes'],critical=(e['core_id'],e['op_id']) in critical))
    for tid,start in resident.items():windows[tid].append((start,result['makespan']+1))
    misses.sort(key=lambda e:(not e['critical'],-e['duration'],-e['size'],e['time'],e['group']))
    return dict(windows=dict(windows),misses=misses,users=dict(users),critical_chain=diagnostic['critical_chain'],start_reconstruction_error=diagnostic['start_reconstruction_max_error'])

def candidates(g,plan,result,family,budget,settings,delay,traced=None):
    if family=='control':
        # Predeclared balanced portfolio of the two strongest previous methods.
        a=old_candidates(g,plan,result,'event',budget//2)
        b=old_candidates(g,plan,result,'split',budget-budget//2)
        out=[];seen={key(plan)}
        for x in a+b:
            h=key(x['plan'])
            if h not in seen:seen.add(h);out.append(x)
        return out,dict(kind='previous_event_split_portfolio')
    d=traced if traced is not None else trace(g.raw,plan,result,settings,delay)
    owner=owner_of(plan);mapping={int(v):s for v,s in plan['node_to_subgraph'].items()}
    groups,_,_,_,_,loads,_=context(g,mapping)
    starts={}
    for c in result['per_core_timeline']:
        for o in c['ops']:
            s=o['subgraph_id']
            if s in groups:starts[s]=min(starts.get(s,float('inf')),o['start'])
    out=[];seen={key(plan)}
    def add(p,move):
        h=key(p)
        if h in seen:return False
        try:structural(g,p)
        except ValueError:return False
        seen.add(h);out.append(dict(plan=p,move=move));return True
    def insert(base,s,c,target):
        seqs,lo,hi=legal_positions(g,base,s,c)
        if lo>hi:return []
        positions=sorted(range(lo,hi+1),key=lambda i:(abs((starts.get(seqs[c][i],result['makespan']) if i<len(seqs[c]) else result['makespan'])-target),i))[:3]
        plans=[]
        for i in positions:
            p=dict(node_to_subgraph=dict(base['node_to_subgraph']),core_schedules=copy.deepcopy(seqs));p['core_schedules'][c].insert(i,s)
            plans.append((p,i))
        return plans
    window_cap=budget if family=='window' else budget//2
    # Existing FIFO windows are proposal hints only; reordering may change them.
    for e in d['misses'][:64]:
        s=e['group']
        if s not in groups:continue
        ws=sorted((w for w in d['windows'].get(e['tensor'],[]) if w[1]>w[0]),key=lambda w:min(abs(w[0]-e['time']),abs(w[1]-1-e['time'])))[:2]
        for begin,end in ws:
            target=begin if e['time']<begin else end-1
            target_group=starts.get(s,0)+target-e['time']
            for p,at in insert(plan,s,owner[s],target_group):
                add(p,dict(kind='fifo_window',group=s,position=at,tensor=e['tensor'],window=[begin,end],old_read=e['time'],critical=e['critical']))
                if len(out)>=window_cap:break
            if len(out)>=window_cap:break
        if len(out)>=window_cap:break
    if family=='joint':
        tensor_score=Counter()
        for e in d['misses']:tensor_score[e['tensor']]+=e['duration']*(4 if e['critical'] else 1)
        for tid in sorted(d['users'],key=lambda t:(-tensor_score[t],t))[:24]:
            ss=[s for s in d['users'][tid] if s in groups]
            ss.sort(key=lambda s:(-d['users'][tid][s],starts.get(s,0),s))
            ss=ss[:3]
            if len(ss)<2:continue
            destinations=sorted({owner[s] for s in ss},key=lambda c:(sum(max(loads[s].values(),default=0) for s in plan['core_schedules'][c]),c))
            for c in destinations:
                base=plan;changes=[]
                target=min(starts.get(s,0) for s in ss)
                for s in sorted(ss,key=lambda s:(starts.get(s,0),s)):
                    options=insert(base,s,c,target)
                    if options:
                        base,at=options[0];changes.append(dict(group=s,from_core=owner[s],to_core=c,position=at))
                if len(changes)>=2:add(base,dict(kind='shared_tensor_group',tensor=tid,moves=changes))
                if len(out)>=budget:break
            if len(out)>=budget:break
    return out,dict(kind=family,critical_chain=d['critical_chain'],start_reconstruction_error=d['start_reconstruction_error'],miss_count=len(d['misses']),window_count=sum(map(len,d['windows'].values())),proposal_count=len(out))
