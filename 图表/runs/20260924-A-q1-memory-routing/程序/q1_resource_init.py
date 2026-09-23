"""Bounded ready-set growth using Pipe work, tensor boundaries and critical rank.

Only constructs an initial partition. No official evaluation, core-local reuse
credit or enumeration. Task boundaries follow one topological traversal.
"""
from collections import defaultdict
import heapq
import math


def resource_partition(g, cores, width=8, max_ops=512):
    if cores < 1 or width < 1 or max_ops < 1:
        raise ValueError('positive bounds required')
    total = defaultdict(float)
    for op in g.ops.values():
        total[op['pipe']] += op['cycles']
    target = max(4*g.same, max(total.values(), default=0)/(8*cores), 1)
    degree = {u: len(g.pred[u]) for u in g.ops}
    ready = [(-g.rank[u], u) for u,d in degree.items() if not d]
    heapq.heapify(ready)
    mapping = {}; block = 0; probes = 0; blocks = []

    def boundary(i, np, nc):
        size, _, ps, cs, final = g.tensors[i]
        incoming = nc > 0 and np == 0
        outgoing = np > 0 and (final or not cs or nc < len(cs))
        return incoming, outgoing, size

    while ready:
        members = set(); counts = {}; loads = defaultdict(float)
        live = defaultdict(int); peak = defaultdict(int); ends = {}; chain = 0.
        duration = 0.; reason = 'exhausted'
        while ready and len(members) < max_ops:
            choices = [heapq.heappop(ready) for _ in range(min(width,len(ready)))]
            options = []
            for _,u in choices:
                probes += 1
                nextloads = dict(loads); nextloads[g.ops[u]['pipe']] = nextloads.get(g.ops[u]['pipe'],0)+g.ops[u]['cycles']
                nextlive = dict(live); nextpeak = dict(peak); updates = {}; saved = 0
                for i in g.incident[u]:
                    size,pos,ps,cs,_ = g.tensors[i]
                    np,nc = counts.get(i,(0,0))
                    before = boundary(i,np,nc)
                    ap,ac = np+int(u in ps),nc+int(u in cs)
                    after = boundary(i,ap,ac); updates[i] = (ap,ac)
                    alone = boundary(i,int(u in ps),int(u in cs))
                    saved += size*(int(before[0])+int(before[1])+int(alone[0])+int(alone[1])-int(after[0])-int(after[1]))
                    for pipe,j in [('PIPE_MTE2',0),('PIPE_MTE3',1)]:
                        nextloads[pipe] = nextloads.get(pipe,0)+(int(after[j])-int(before[j]))*math.ceil(size/g.bandwidth)
                    # Conservative ready-traversal lifetime proxy, not official allocation.
                    if i not in counts: nextlive[pos] = nextlive.get(pos,0)+size
                    nextpeak[pos] = max(nextpeak.get(pos,0),nextlive.get(pos,0))
                    if ac == len(cs) and (ap+ac)>0 and (nc < len(cs) or i not in counts):
                        nextlive[pos] = nextlive.get(pos,0)-size
                finish = g.ops[u]['cycles']+max((ends[p] for p in g.pred[u] if p in ends),default=0)
                nextchain = max(chain,finish)
                pressure = sum(max(0,nextpeak.get(p,0)-cap) for p,cap in g.capacity.items())
                estimate = max(max(nextloads.values(),default=0),nextchain)+2*pressure/g.bandwidth
                dependent = bool(g.pred[u] & members)
                oldwork = max((loads[p] for p in total),default=0)
                newwork = max((nextloads.get(p,0) for p in total),default=0)
                parallel_loss = 0 if dependent else max(0,newwork-max(oldwork,g.ops[u]['cycles']))
                utility = saved/g.bandwidth + (g.same if dependent else 0)-parallel_loss-2*pressure/g.bandwidth
                options.append((utility,g.rank[u],-u,u,nextloads,nextlive,nextpeak,updates,finish,nextchain,estimate,saved,dependent))
            best = max(options,key=lambda x:x[:3]); u = best[3]
            for item in choices:
                if item[1] != u: heapq.heappush(ready,item)
            if members and (best[10] > target and not
                    (best[12] and best[10] <= 1.5*target and best[11]/g.bandwidth >= best[10]-duration)):
                heapq.heappush(ready,(-g.rank[u],u));reason='work_target';break
            mapping[u] = block; members.add(u)
            loads=defaultdict(float,best[4]);live=defaultdict(int,best[5]);peak=defaultdict(int,best[6])
            counts.update(best[7]);ends[u]=best[8];chain=best[9];duration=best[10]
            for v in sorted(g.succ[u]):
                degree[v] -= 1
                if degree[v] == 0: heapq.heappush(ready,(-g.rank[v],v))
        blocks.append({'ops':len(members),'estimated_cycles':duration,'stop':reason if len(members)<max_ops else 'op_safety_cap'})
        block += 1
    if set(mapping) != set(g.ops): raise ValueError('incomplete topological growth')
    g.view(mapping)  # Quotient must remain acyclic.
    g.resource_init_stats = {'target_cycles':target,'width':width,'max_ops':max_ops,'probes':probes,'blocks':blocks}
    return mapping
