"""Work/communication-frontier partitions, vector packing, and varied list scheduling.

All scores here are proposal heuristics, never reported NPU makespans.
Scene A has no private-cache reuse across separate Tasks even on the same core.
"""
import bisect,math,random
from collections import defaultdict
from q1_solver import topological
from q1_insertion import earliest_gap

def components(g):
    seen=set();groups=[]
    for u in g.order:
        if u in seen:continue
        stack=[u];seen.add(u);group=[]
        while stack:
            v=stack.pop();group.append(v)
            for w in sorted(g.pred[v]|g.succ[v]):
                if w not in seen:seen.add(w);stack.append(w)
        groups.append(sorted(group,key=g.pos.get))
    return groups

def schedule(g,mapping,k,rng,variant=0):
    duration,_,(_,pred,succ,order)=g.costs(mapping)
    rank={};breadth={}
    for s in reversed(order):
        rank[s]=duration[s]+max((g.same+rank[v] for v in succ[s]),default=0)
        breadth[s]=duration[s]+sum(duration[v] for v in succ[s])
    weight=[0,.15,.4][variant%3]
    priority={s:rank[s]+weight*breadth[s] for s in order}
    if variant>=3:
        priority={s:v*rng.uniform(.9,1.1) for s,v in priority.items()}
    events=[[] for _ in range(k)];finish={};assigned={};loads=[0.]*k
    for s in topological(pred,succ,priority):
        options=[]
        for c in range(k):
            ready=max((finish[p]+(g.cross if assigned[p]!=c else 0) for p in pred[s]),default=0)
            start,index=earliest_gap(events[c],ready,duration[s],g.same)
            end=start+duration[s]
            options.append((end+weight*.1*loads[c],rng.random() if variant>=3 else c,c,start,index,end))
        _,_,c,start,index,end=min(options)
        events[c].insert(index,(start,end,s));finish[s]=end;assigned[s]=c;loads[c]+=duration[s]
    return dict(node_to_subgraph={str(u):mapping[u] for u in sorted(mapping)},core_schedules=[[s for _,_,s in x] for x in events])

def frontier_mapping(g,k,rng,index,nodes=None,target_groups=None,max_ops=None):
    members=set(g.ops) if nodes is None else set(nodes)
    if nodes is None and index%3:
        priorities={u:g.rank[u]*rng.uniform(.7,1.3) for u in g.order}
        order=topological(g.pred,g.succ,priorities)
    else:order=[u for u in g.order if u in members]
    pos={u:i for i,u in enumerate(order)};n=len(order)
    prefix=[0.]
    for u in order:prefix.append(prefix[-1]+max(1,g.ops[u]['cycles']))
    delta=[0.]*(n+1)
    for size,_,ps,cs,_ in g.tensors:
        points=[pos[u] for u in (ps|cs)&members]
        if len(points)>1:
            lo,hi=min(points),max(points);delta[lo]+=size;delta[hi]-=size
    active=0.;boundary=[]
    for x in delta[:n]:active+=x;boundary.append(active/g.bandwidth)
    groups=target_groups or max(k,round(k*2**rng.uniform(0,4)))
    target=max(1,prefix[-1]/groups);mapping={};start=0;gid=0
    while start<n:
        if prefix[-1]-prefix[start]<=target*1.35:end=n
        else:
            lo=max(start+1,bisect.bisect_left(prefix,prefix[start]+target*.65))
            hi=min(n,max(lo,bisect.bisect_left(prefix,prefix[start]+target*1.35)))
            # Work balance and live boundary cost; no enumeration of partitions.
            end=min(range(lo,hi+1),key=lambda j:(boundary[j-1]*(.5+index%4)+abs(prefix[j]-prefix[start]-target),j))
        if max_ops is not None:end=min(end,start+max_ops)
        for u in order[start:end]:mapping[u]=gid
        gid+=1;start=end
    return mapping

def packing(g,groups,k,rng,index):
    vectors=[];inputs=[]
    for nodes in groups:
        v=defaultdict(float);ts=set()
        for u in nodes:
            v[g.ops[u]['pipe']]+=g.ops[u]['cycles'];ts.update(g.incident[u])
        vectors.append(v);inputs.append({t for t in ts if not g.tensors[t][2]})
    order=sorted(range(len(groups)),key=lambda j:(-max(vectors[j].values())*rng.uniform(.8,1.2),j))
    loads=[defaultdict(float) for _ in range(k)];used=[set() for _ in range(k)];assignment={}
    affinity=[0,.25,1,2][index%4]
    for j in order:
        options=[]
        for c in range(k):
            cost=max(loads[c][p]+vectors[j].get(p,0) for p in set(loads[c])|set(vectors[j]))
            fresh=sum(g.tensors[t][0] for t in inputs[j]-used[c])/g.bandwidth
            options.append((cost+affinity*fresh,rng.random(),c))
        c=min(options)[2];assignment[j]=c;used[c].update(inputs[j])
        for p,x in vectors[j].items():loads[c][p]+=x
    # Bounded stochastic relocation improves vector balance without factorial search.
    for _ in range(2*len(groups)):
        j=rng.randrange(len(groups));src=assignment[j];dst=rng.randrange(k)
        if src==dst:continue
        before=max(max(x.values(),default=0) for x in loads)
        for p,x in vectors[j].items():loads[src][p]-=x;loads[dst][p]+=x
        after=max(max(x.values(),default=0) for x in loads)
        if after<before:assignment[j]=dst
        else:
            for p,x in vectors[j].items():loads[src][p]+=x;loads[dst][p]-=x
    mapping={};schedules=[[] for _ in range(k)];gid=0
    # Keep whole components; variable batching controls cache pressure without cuts.
    factor=[1,2,4,8][(index//4)%4]
    target=sum(sum(x.values()) for x in vectors)/max(1,k*factor)
    for c in range(k):
        chosen=[j for j in order if assignment[j]==c];batch=[];work=0
        for j in chosen:
            w=sum(vectors[j].values())
            if batch and work+w>target:
                for u in batch:mapping[str(u)]=gid
                schedules[c].append(gid);gid+=1;batch=[];work=0
            batch.extend(groups[j]);work+=w
        if batch:
            for u in batch:mapping[str(u)]=gid
            schedules[c].append(gid);gid+=1
    return dict(node_to_subgraph=mapping,core_schedules=schedules)

class Generator:
    def __init__(self,g,k,seed=0):
        self.g=g;self.k=k;self.rng=random.Random(seed);self.groups=components(g)
        self.arms=['frontier','boundary','list_order']+(['vector_packing'] if len(self.groups)>1 else [])
        self.indices=defaultdict(int)
    def propose(self,arm,incumbent):
        g,k,rng=self.g,self.k,self.rng;idx=self.indices[arm];self.indices[arm]+=1
        mapping={int(u):s for u,s in incumbent['node_to_subgraph'].items()}
        if arm=='vector_packing':return packing(g,self.groups,k,rng,idx)
        if arm=='frontier':mapping=frontier_mapping(g,k,rng,idx)
        elif arm=='boundary':
            groups,pred,succ,_=g.view(mapping)
            if idx%2 and len(groups)>1:
                affinity=defaultdict(float)
                for size,_,ps,cs,_ in g.tensors:
                    for a in {mapping[u] for u in ps}:
                        for b in {mapping[u] for u in cs}-{a}:affinity[a,b]+=size
                choices=sorted(affinity,key=lambda x:(-affinity[x],x))[:32]
                if not choices:return None
                a,b=rng.choice(choices);mapping={u:a if s==b else s for u,s in mapping.items()}
            else:
                choices=sorted((s for s in groups if len(groups[s])>=2),key=lambda s:-sum(g.ops[u]['cycles'] for u in groups[s]))[:8]
                if not choices:return None
                s=rng.choice(choices);part=frontier_mapping(g,k,rng,idx,groups[s],2)
                new=max(groups)+1
                mapping.update({u:new+p for u,p in part.items()})
            g.view(mapping)  # Reject contraction cycles before scheduling.
        return schedule(g,mapping,k,rng,idx%6)
