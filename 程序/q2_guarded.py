"""r02: protected migration incumbent, criticality-gated lifetime ordering, local J.

Candidate proxies never replace the original official scene-B evaluator.
"""
from collections import Counter,defaultdict
import copy
import heapq
import random
import time
from q2_solver import SceneBGraph,context,place,order_plan,proxy,owner_of,greedy_partition,topological,proposal,DEFAULTS
from q2_evaluator import evaluate,key

VARIANTS=('protected','legacy_L','guarded','full')
PARAMETERS={'budget':12,'block_sizes':[16,64,256],'critical_tolerance':0.05,
            'ready_window':32,'pool_limit':6,'pool_attempts':48,'seed_values':[0,1]}


def guarded_order(g,plan,tolerance=.05):
    if not 0<=tolerance<=1:raise ValueError('Invalid critical tolerance')
    mapping={int(v):s for v,s in plan['node_to_subgraph'].items()};owner=owner_of(plan)
    groups,pred,succ,_,incident,_,ranks=context(g,mapping)
    count=Counter((owner[s],i) for s in groups for i in incident[s])
    live=[set() for _ in plan['core_schedules']];resident=[defaultdict(int) for _ in live]
    degree={s:len(pred[s]) for s in groups};ready=[(-ranks[s],s) for s in groups if not degree[s]]
    heapq.heapify(ready);seq=[[] for _ in live]
    while ready:
        options=[heapq.heappop(ready) for _ in range(min(32,len(ready)))]
        threshold=(1-tolerance)*max(ranks[s] for _,s in options)
        allowed=[s for _,s in options if ranks[s]>=threshold]
        def score(s):
            c=owner[s];add=defaultdict(int);free=defaultdict(int)
            for i in incident[s]:
                size,tier,*_=g.tensors[i]
                if i not in live[c]:add[tier]+=size
                if count[c,i]==1:free[tier]+=size
            pressure=sum(max(0,resident[c][r]+add[r]-cap)/cap for r,cap in g.capacity.items())
            delta=sum((add[r]-free[r])/cap for r,cap in g.capacity.items())
            return pressure+delta,-ranks[s],s
        chosen=min(allowed,key=score)
        for item in options:
            if item[1]!=chosen:heapq.heappush(ready,item)
        c=owner[chosen];seq[c].append(chosen)
        for i in incident[chosen]:
            size,tier,*_=g.tensors[i]
            if i not in live[c]:live[c].add(i);resident[c][tier]+=size
            count[c,i]-=1
            if count[c,i]==0:live[c].remove(i);resident[c][tier]-=size
        for v in sorted(succ[chosen]):
            degree[v]-=1
            if degree[v]==0:heapq.heappush(ready,(-ranks[v],v))
    return {'node_to_subgraph':dict(plan['node_to_subgraph']),'core_schedules':seq}


def structural(g,plan):
    mapping={int(v):s for v,s in plan['node_to_subgraph'].items()}
    groups,pred,succ,_,_,_,_=context(g,mapping)
    seq=plan['core_schedules'];flat=[s for q in seq for s in q]
    if len(flat)!=len(set(flat)) or set(flat)!=set(groups):raise ValueError('Invalid coverage')
    for q in seq:
        for u,v in zip(q,q[1:]):pred[v].add(u);succ[u].add(v)
    return topological(pred,succ)


def critical_proxy(g,plan):
    """Conservative group serialization proxy, not a lower bound or exact time."""
    mapping={int(v):s for v,s in plan['node_to_subgraph'].items()};owners=owner_of(plan)
    _,pred,succ,_,_,loads,_=context(g,mapping)
    for q in plan['core_schedules']:
        for u,v in zip(q,q[1:]):pred[v].add(u);succ[u].add(v)
    end={}
    for s in topological(pred,succ):
        end[s]=max(loads[s].values(),default=0)+max((end[u]+(g.delay if owners[u]!=owners[s] else 0) for u in pred[s]),default=0)
    return max(proxy(g,plan),max(end.values(),default=0))


def local_pool(g,plan,cores,rng,limit=6):
    """At most one migrated group or one exchange; outside order is preserved."""
    mapping={int(v):s for v,s in plan['node_to_subgraph'].items()};owners=owner_of(plan)
    groups,_,_,_,incident,_,ranks=context(g,mapping)
    ranked=sorted(groups,key=lambda s:(-(ranks[s]+sum(g.tensors[i][0] for i in incident[s])/g.bandwidth),s))
    region=ranked[:4]
    if len(ranked)>4:region+=rng.sample(ranked[4:],min(2,len(ranked)-4))
    moves=[(s,c) for s in region for c in range(cores) if owners[s]!=c];rng.shuffle(moves)
    candidates=[];seen={key(plan)}
    for attempt in range(min(48,max(1,len(moves)*3))):
        if not moves:break
        s,c=moves[attempt%len(moves)];trial=copy.deepcopy(plan);src=owners[s]
        old=trial['core_schedules'][src].index(s)
        if attempt%3==2 and trial['core_schedules'][c]:
            at=rng.randrange(len(trial['core_schedules'][c]));v=trial['core_schedules'][c][at]
            trial['core_schedules'][src][old]=v;trial['core_schedules'][c][at]=s
            move={'kind':'exchange','groups':[s,v]}
        else:
            trial['core_schedules'][src].pop(old)
            at=rng.randrange(len(trial['core_schedules'][c])+1)
            trial['core_schedules'][c].insert(at,s);move={'kind':'migrate_insert','group':s,'core':c,'at':at}
        try:structural(g,trial)
        except ValueError:continue
        h=key(trial)
        if h in seen:continue
        seen.add(h);candidates.append({'plan':trial,'plan_sha256':h,'proxy':critical_proxy(g,trial),'legacy_proxy':proxy(g,trial),'move':move})
        if len(candidates)>=limit:break
    return candidates


def solve(raw,settings,delay,cores,migration,variant='guarded',seed=0,on_candidate=None):
    if variant not in VARIANTS or cores not in range(2,6):raise ValueError('Invalid variant/cores')
    if len(migration['core_schedules'])!=cores:raise ValueError('Migration cores mismatch')
    g=SceneBGraph(raw,settings,delay);rng=random.Random(seed);rows=[];best_plan=best_result=None
    seen={};pools=[];initial=[]
    def assess(plan,label):
        nonlocal best_plan,best_result
        h=key(plan);start=time.perf_counter();row={'slot':len(rows),'label':label,'plan_sha256':h,'cached':h in seen}
        if h in seen:result,err=seen[h]
        else:
            try:result=evaluate(raw,plan,settings,delay);err=None
            except (ValueError,RuntimeError) as exc:result=None;err=str(exc)
        # Retain only compact results in the cache; repeated proposals may need
        # one more evaluation if they ever become the best (normally impossible).
        if result is not None:
            score=(result['makespan'],result['data_movement_bytes']['added_copy_bytes'])
            row.update(status='success',makespan=score[0],added_copy_bytes=score[1],accepted=False)
            if best_result is None or score<(best_result['makespan'],best_result['data_movement_bytes']['added_copy_bytes']):
                best_plan=copy.deepcopy(plan);best_result=result;row['accepted']=True
            seen[h]=({'makespan':score[0],'data_movement_bytes':dict(result['data_movement_bytes'])},None)
        else:row.update(status='error',error=err);seen[h]=(None,err)
        row['seconds']=time.perf_counter()-start;rows.append(row)
        if on_candidate:on_candidate(plan,row)
        return row
    migration_row=assess(migration,'migration')
    whole={'node_to_subgraph':{str(v):0 for v in g.ops},'core_schedules':[[0]]+[[] for _ in range(cores-1)]}
    assess(whole,'whole')
    for size in (16,64,256):
        mapping=greedy_partition(g,cores,size);owners=place(g,mapping,cores,True)
        plan=order_plan(g,mapping,owners,cores,False);assess(plan,'critical_'+str(size));initial.append(plan)
    anchors=[migration,copy.deepcopy(best_plan),initial[0]]
    for i,anchor in enumerate(anchors):
        if variant in ('guarded','full'):trial=guarded_order(g,anchor)
        elif variant=='legacy_L':
            mapping={int(v):s for v,s in anchor['node_to_subgraph'].items()}
            trial=order_plan(g,mapping,owner_of(anchor),cores,True)
        else:
            trial=copy.deepcopy(anchor)
            for _ in range(24):
                try:trial,_=proposal(g,anchor,cores,rng,'',DEFAULTS)
                except ValueError:continue
                if key(trial) not in seen:break
        assess(trial,'order_'+str(i))
    for i in range(4):
        trial=None
        if variant=='full':
            pool=local_pool(g,best_plan,cores,rng)
            pools.append({'slot':len(rows),'incumbent_sha256':key(best_plan),'candidates':pool})
            if pool:trial=min(pool,key=lambda x:(x['proxy'],x['plan_sha256']))['plan']
        if trial is None:
            for _ in range(24):
                try:trial,_=proposal(g,best_plan,cores,rng,'',DEFAULTS)
                except ValueError:continue
                if key(trial) not in seen:break
            if trial is None:trial=copy.deepcopy(best_plan)
        assess(trial,('joint_' if variant=='full' else 'ordinary_')+str(i))
    if best_result is None:raise RuntimeError('No valid candidate')
    if migration_row['status']=='success':assert (best_result['makespan'],best_result['data_movement_bytes']['added_copy_bytes']) <= (migration_row['makespan'],migration_row['added_copy_bytes'])
    return best_plan,best_result,{'variant':variant,'seed':seed,'parameters':PARAMETERS,'evaluations':rows,
        'opportunities':len(rows),'official_calls':sum(not r['cached'] for r in rows),'migration':migration_row,'pools':pools}
