"""Compressed local DDR phase replay, not an operation-level global simulator.

Local Pipe overlaps are frozen. DDR overlap stretches an entire local phase,
including any concurrent compute: this deliberate approximation can overpredict.
Each Task has at most 64 phases; no candidate official outcome is used.
"""
from collections import defaultdict


def profile(task, limit=64):
    from schedule_step3 import _uses_ddr_bandwidth
    local = task['step3']
    length = local['makespan']
    events = defaultdict(float)
    events[0] = events[length] = 0.
    for u, op in task['op_by_id'].items():
        if _uses_ddr_bandwidth(op, task['in_tids'], task['out_tids'], task['tensor_by_id']):
            events[local['op_start'][u]] += 1
            events[local['op_end'][u]] -= 1
    points = sorted(events)
    segments, active = [], 0.
    for a,b in zip(points,points[1:]):
        active += events[a]
        if b>a:
            segments.append((a,b,active))
    if len(segments)<=limit:
        return [(b-a,n) for a,b,n in segments]
    # Equal-time bins preserve the integral of local active-DDR concurrency.
    bins = [0.] * limit
    width = length/limit
    for a,b,n in segments:
        for i in range(max(0,int(a/width)),min(limit,int(b/width)+1)):
            bins[i] += max(0.,min(b,(i+1)*width)-max(a,i*width))*n/width
    return [(width,n) for n in bins]


def phase_time(g, plan, profiles):
    mapping = {int(u):s for u,s in plan['node_to_subgraph'].items()}
    pred = g.view(mapping)[1]
    seqs = plan['core_schedules']
    owner = {s:c for c,seq in enumerate(seqs) for s in seq}
    index = [0]*len(seqs)
    active, finished = {}, {}
    now = 0.
    bound = 3*(sum(len(p) for p in profiles.values())+len(profiles)+1)
    for _ in range(bound):
        for s,(i,remaining) in list(active.items()):
            if remaining <= 1e-7:
                if i+1<len(profiles[s]):
                    active[s] = (i+1,float(profiles[s][i+1][0]))
                else:
                    finished[s] = now
                    del active[s]
                    index[owner[s]] += 1
        if len(finished)==len(profiles):
            return now
        releases = []
        for c,seq in enumerate(seqs):
            if index[c]>=len(seq):
                continue
            s = seq[index[c]]
            if s in active or not pred[s]<=finished.keys():
                continue
            ready = max((finished[p]+(g.cross if owner[p]!=c else 0) for p in pred[s]),default=0)
            if index[c]:
                ready = max(ready,finished[seq[index[c]-1]]+g.same)
            if ready<=now+1e-7:
                active[s] = (0,float(profiles[s][0][0]))
            else:
                releases.append(ready)
        pressure = {s:profiles[s][i][1] for s,(i,_) in active.items()}
        total = sum(pressure.values())
        # Each Task's local reference already shares bandwidth among its own COPYs.
        rates = {s:min(1.,max(1.,n)/max(1.,total)) if n else 1. for s,n in pressure.items()}
        events = [r/rates[s] for s,(_,r) in active.items()]+[r-now for r in releases]
        if not events:
            raise ValueError('Infeasible phase replay')
        dt = min(events)
        active = {s:(i,r-dt*rates[s]) for s,(i,r) in active.items()}
        now += dt
    raise RuntimeError('Phase replay bound exceeded')
