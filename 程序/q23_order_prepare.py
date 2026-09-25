"""Experimental immutable ordering preparation; official evaluation unchanged.

Cache only mapping-dependent structure. Owners, live sets, remaining counts,
resident bytes, ready heap and priorities are rebuilt on every ordering call.
"""
import hashlib,pickle,heapq,time
from collections import Counter,defaultdict,OrderedDict
from q23_selective_reuse import GenerationReuse

class OrderingPreparation:
    def __init__(self,g,max_bytes=32*1024**2):
        import q2_solver
        self.g=g;self.module=q2_solver;self.limit=max_bytes
        self.entries=OrderedDict();self.bytes=0;self.stats=Counter()
    def prepare(self,g,mapping):
        t=time.perf_counter();k=hashlib.sha256(pickle.dumps(mapping,protocol=5)).digest()
        self.stats['calls']+=1
        if k in self.entries:
            value,b=self.entries.pop(k);self.entries[k]=(value,b);self.stats['hits']+=1
        else:
            groups,pred,succ,_,incident,loads,ranks=self.module.context(g,mapping)
            # Private tuples/dicts never returned to external callers or mutated.
            value=(tuple(groups),{s:tuple(pred[s]) for s in groups},
                   {s:tuple(sorted(succ[s])) for s in groups},
                   {s:tuple((i,g.tensors[i][0],g.tensors[i][1]) for i in incident[s]) for s in groups},dict(ranks))
            b=len(pickle.dumps(value,protocol=5));self.stats['misses']+=1
            if b<=self.limit//4:
                while self.entries and self.bytes+b>self.limit:
                    _,(_,old)=self.entries.popitem(last=False);self.bytes-=old;self.stats['evictions']+=1
                self.entries[k]=(value,b);self.bytes+=b
            self.stats['peak_payload_bytes']=max(self.stats['peak_payload_bytes'],self.bytes)
        self.stats['prepare_seconds']+=time.perf_counter()-t
        return value
    def __enter__(self):
        self.original=self.module.order_plan
        self.module.order_plan=self.order_plan
        # Retain the previous generation cache in BOTH benchmark arms.
        self.generation=GenerationReuse(self.g)
        self.generation.__enter__()
        return self
    def __exit__(self,*exc):
        self.generation.__exit__(*exc);self.module.order_plan=self.original
        self.entries.clear();self.bytes=0

    def order_plan(self, g, mapping, owners, cores, lifetime=True, window=32, weight=1.0,
                   random_priority=None):
        """Project ONE global legal group order to cores; no core-graph contraction.

        Lifetime is a group-level no-spill proxy. External COPY_OUT timing and Pipe
        overlap are resolved only by the official evaluator.
        """
        if g is not self.g: return self.original(g,mapping,owners,cores,lifetime,window,weight,random_priority)
        groups, pred, succ, incident, ranks = self.prepare(g, mapping)
        counts = Counter()
        for s in groups:
            for i, size, tier in incident[s]:
                counts[owners[s], i] += 1
        live = [set() for _ in range(cores)]
        resident = [defaultdict(int) for _ in range(cores)]
        degree = {s: len(pred[s]) for s in groups}
        priority = random_priority or ranks
        ready = [(-priority[s], s) for s in groups if degree[s] == 0]
        heapq.heapify(ready)
        schedules = [[] for _ in range(cores)]
        rank_scale = max(ranks.values(), default=1) or 1
        while ready:
            candidates = [heapq.heappop(ready) for _ in range(min(window if lifetime else 1, len(ready)))]
            def score(item):
                _, s = item; c = owners[s]
                added, freed = defaultdict(int), defaultdict(int)
                for i, size, tier in incident[s]:
                    if i not in live[c]: added[tier] += size
                    if counts[c, i] == 1: freed[tier] += size
                pressure = sum(max(0, resident[c][r] + added[r] - cap) / cap
                               for r, cap in g.capacity.items())
                delta = sum((added[r] - freed[r]) / cap for r, cap in g.capacity.items())
                return (weight * (pressure + delta) - ranks[s] / rank_scale, -ranks[s], s)
            chosen = min(candidates, key=score) if lifetime else candidates[0]
            for item in candidates:
                if item != chosen: heapq.heappush(ready, item)
            s = chosen[1]; c = owners[s]; schedules[c].append(s)
            for i, size, tier in incident[s]:
                if i not in live[c]: live[c].add(i); resident[c][tier] += size
                counts[c, i] -= 1
                if counts[c, i] == 0: live[c].remove(i); resident[c][tier] -= size
            for v in sorted(succ[s]):
                degree[v] -= 1
                if degree[v] == 0: heapq.heappush(ready, (-priority[v], v))
        if sum(map(len, schedules)) != len(groups): raise ValueError('Cyclic group order')
        return {'node_to_subgraph': {str(v): mapping[v] for v in sorted(mapping)},
                'core_schedules': schedules}
