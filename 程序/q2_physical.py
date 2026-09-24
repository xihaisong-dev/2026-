"""Scene-B physical tensor instances and legal insertion neighborhoods.

Uses unchanged official preparation (local Step1/2/3). Such calls are counted
separately from the global B evaluator. Local lifetimes are exact locally;
the network timing proxy is approximate, never a replacement for B scoring.
"""
from collections import defaultdict
import copy
import time
from q2_evaluator import key
from q2_solver import context,owner_of,topological
from q2_guarded import structural
from q1_pipe_event import replay_network


def intervals(task,starts=None,ends=None):
    """Distinct spill incarnations; allocate at producer issue, free at last finish."""
    starts=task['step3']['op_start'] if starts is None else starts
    ends=task['step3']['op_end'] if ends is None else ends
    producers=defaultdict(set);consumers=defaultdict(set)
    for op,ids in task['out_tids'].items():
        for tid in ids:producers[tid].add(op)
    for op,ids in task['in_tids'].items():
        for tid in ids:consumers[tid].add(op)
    result=[]
    for tid,tensor in task['tensor_by_id'].items():
        if tensor['pos']=='DDR' or not (producers[tid] or consumers[tid]):continue
        ps=producers[tid];cs=consumers[tid]
        start=min((starts[o] for o in ps),default=0)
        end=max((ends[o] for o in cs or ps),default=start)
        if end<start:raise AssertionError('Negative lifetime')
        first=min(ps,key=lambda o:(starts[o],o)) if ps else None
        last=max(cs or ps,key=lambda o:(ends[o],o)) if cs or ps else None
        result.append({'tid':tid,'logical_tid':tensor.get('logical_tid',tid),'pos':tensor['pos'],
          'size':tensor['size'],'start':start,'end':end,'byte_cycles':tensor['size']*(end-start),
          'first_op':first,'last_op':last,'first_group':task['op_subgraph'].get(first),
          'last_group':task['op_subgraph'].get(last),'producer_op':task['op_by_id'][first]['op'] if first is not None else None})
    return result


def occupancy(lives,capacity):
    events=defaultdict(lambda:defaultdict(int));area=defaultdict(int)
    for row in lives:
        area[row['pos']]+=row['byte_cycles']
        if row['start']==row['end']:continue
        events[row['start']][row['pos']]+=row['size'];events[row['end']][row['pos']]-=row['size']
    used=defaultdict(int);peak=defaultdict(int)
    for t in sorted(events):
        for pos,delta in events[t].items():used[pos]+=delta;peak[pos]=max(peak[pos],used[pos])
    if any(used.values()):raise AssertionError('Unclosed lifetimes')
    return {'area_byte_cycles':dict(area),'peak_bytes':{p:peak[p] for p in capacity},
            'normalized_area_cycles':sum(area[p]/cap for p,cap in capacity.items())}


def event_proxy(tasks,links,bandwidth,delay):
    from schedule_step3 import _op_duration,_uses_ddr_bandwidth,PIPE_SLOTS
    if PIPE_SLOTS!=1:raise ValueError('Network proxy assumes one slot per Pipe')
    pred={};base={};ddr=set()
    for c,t in tasks.items():
        for o,op in t['op_by_id'].items():
            v=(c,o);pred[v]={(c,u):0. for u in t['op_preds'][o]}
            base[v]=_op_duration(op,t['in_tids'],t['out_tids'],t['tensor_by_id'],bandwidth)
            if _uses_ddr_bandwidth(op,t['in_tids'],t['out_tids'],t['tensor_by_id']):ddr.add(v)
        for seq in t['pipe_ops'].values():
            for a,b in zip(seq,seq[1:]):pred[c,b][c,a]=0.
    for link in links:pred[link['target_core'],link['target_copy_in_id']][link['source_core'],link['source_copy_out_id']]=delay
    succ={v:set() for v in pred}
    for v,ps in pred.items():
        for u in ps:succ[u].add(v)
    order=topological({v:set(ps) for v,ps in pred.items()},succ)
    return replay_network(order,pred,base,ddr,passes=3)[0]


class PhysicalScorer:
    def __init__(self,raw,settings,delay):
        self.raw,self.settings,self.delay=raw,settings,delay
        self.cache={};self.prepare_calls=0;self.prepare_seconds=0.;self.local_tasks=0

    def prepare(self,plan):
        from multicore_cut_evaluate_problem_2 import _build_scene_b_tasks
        self.prepare_calls+=1;self.local_tasks+=len(plan['core_schedules']);start=time.perf_counter()
        try:return _build_scene_b_tasks(self.raw,plan,self.settings['bandwidth'],self.settings['capacity'])
        finally:self.prepare_seconds+=time.perf_counter()-start

    def score(self,plan):
        h=key(plan)
        if h in self.cache:return self.cache[h]
        try:
            tasks,links,_,traffic,_=self.prepare(plan)
            lives=[dict(row,core=c) for c,t in tasks.items() for row in intervals(t)]
            profiles={c:occupancy([r for r in lives if r['core']==c],self.settings['capacity']) for c in tasks}
            area=sum(p['normalized_area_cycles'] for p in profiles.values())
            # Differential check against actual local alloc/free events, including reincarnations.
            for c,t in tasks.items():
                opened={};measured=defaultdict(int)
                for e in t['step3']['memory_events']:
                    if e['kind'] in ('alloc','initial_alloc'):opened[e['tid']]=e['time']
                    elif e['kind']=='free':measured[e['pos']]+=e['size']*(e['time']-opened.pop(e['tid']))
                if opened:raise AssertionError('Official lifetime not closed')
                expected=profiles[c]['area_byte_cycles']
                if any(measured[p]!=expected.get(p,0) for p in self.settings['capacity']):raise AssertionError('Local lifetime area mismatch')
            score={'status':'success','proxy':event_proxy(tasks,links,self.settings['bandwidth'],self.delay),
              'normalized_area_cycles':area,'traffic':traffic,'instances':len(lives),
              'reload_instances':sum(r['tid']!=r['logical_tid'] for r in lives),
              'boundary_copy_instances':sum(r['producer_op']=='COPY_IN' for r in lives),
              'hot_lifetimes':sorted(lives,key=lambda r:(-r['byte_cycles'],r['core'],r['tid']))[:32],
              'lifetime_area_matches_official_events':True}
        except (ValueError,RuntimeError) as e:score={'status':'error','error':str(e)}
        self.cache[h]=score;return score

    def actual_lifetimes(self,plan,result):
        tasks,_,_,traffic,_=self.prepare(plan)
        if traffic!=result['data_movement_bytes']:raise AssertionError('Preparation traffic mismatch')
        output={}
        for timeline in result['per_core_timeline']:
            c=timeline['core_id'];starts={o['op_id']:o['start'] for o in timeline['ops']};ends={o['op_id']:o['end'] for o in timeline['ops']}
            lives=intervals(tasks[c],starts,ends);profile=occupancy(lives,self.settings['capacity'])
            if any(profile['peak_bytes'][p]>cap for p,cap in self.settings['capacity'].items()):raise AssertionError('Global residency exceeds capacity')
            output[c]={'intervals':lives,**profile}
        return output


def legal_positions(g,plan,group,destination):
    """Exact interval for insertion under the conservative group-order DAG."""
    mapping={int(o):s for o,s in plan['node_to_subgraph'].items()}
    _,pred,succ,*_=context(g,mapping)
    seqs=[[s for s in q if s!=group] for q in plan['core_schedules']]
    for q in seqs:
        for a,b in zip(q,q[1:]):pred[b].add(a);succ[a].add(b)
    # Incoming/outgoing intrinsic edges of group stay, its old order edges do not.
    def reach(edges):
        seen=set();todo=list(edges[group])
        while todo:
            v=todo.pop()
            if v==group:raise ValueError('Base order cycle')
            if v not in seen:seen.add(v);todo.extend(edges[v])
        return seen
    ancestors,descendants=reach(pred),reach(succ);q=seqs[destination]
    lo=max((i+1 for i,s in enumerate(q) if s in ancestors),default=0)
    hi=min((i for i,s in enumerate(q) if s in descendants),default=len(q))
    return seqs,lo,hi


def candidate_pool(g,plan,rng,mode,physical=None,limit=6):
    owners=owner_of(plan);mapping={int(o):s for o,s in plan['node_to_subgraph'].items()}
    groups,_,_,_,incident,_,ranks=context(g,mapping)
    hot=defaultdict(float)
    for r in (physical or {}).get('hot_lifetimes',[]):
        for s in (r['first_group'],r['last_group']):
            if s in groups:hot[s]+=r['byte_cycles']/g.capacity[r['pos']]
    if mode=='life':priority=sorted(groups,key=lambda s:(-hot[s],-ranks[s],s))
    else:priority=sorted(groups,key=lambda s:(-(ranks[s]+sum(g.tensors[i][0] for i in incident[s])/g.bandwidth),s))
    # Diversify deterministic tie/position exploration with the fixed seed.
    region=priority[:16];tail=priority[16:];rng.shuffle(tail);region+=tail[:16]
    pool=[];seen={key(plan)};attempts=0
    for s in region:
        destinations=[owners[s]] if mode=='life' else [c for c in range(len(plan['core_schedules'])) if c!=owners[s]]
        rng.shuffle(destinations)
        for c in destinations:
            seqs,lo,hi=legal_positions(g,plan,s,c)
            if lo>hi:continue
            positions=list(dict.fromkeys([lo,hi,(lo+hi)//2]));rng.shuffle(positions)
            for at in positions:
                trial={'node_to_subgraph':dict(plan['node_to_subgraph']),'core_schedules':copy.deepcopy(seqs)}
                trial['core_schedules'][c].insert(at,s);h=key(trial)
                if h in seen:continue
                attempts+=1;structural(g,trial);seen.add(h)
                pool.append({'plan':trial,'plan_sha256':h,'move':{'group':s,'from':owners[s],'to':c,'position':at,'legal_interval':[lo,hi]},'mode':mode})
                if len(pool)>=limit:return pool
    return pool
