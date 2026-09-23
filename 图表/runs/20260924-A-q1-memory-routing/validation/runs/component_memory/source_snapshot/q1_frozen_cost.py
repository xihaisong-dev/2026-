"""Frozen candidate scoring and a calibrated, coarse shared-DDR fluid proxy.

This is not the official event simulator: it spreads each task's boundary traffic
uniformly over its isolated lifetime, ignores spill phases, and uses only the
incumbent to fit one nonnegative correction coefficient.
"""
import copy
import hashlib
from q1_search_tools import canonical, replay


def state_hash(g):
    return hashlib.sha256(canonical({
        'observations': sorted((list(k), v) for k, v in g.local_observations.items()),
        'ratios': dict(g.ratios), 'enabled': g.enabled, 'calibrated': g.calibrated,
        'bandwidth': g.bandwidth, 'capacity': g.capacity, 'waits': [g.cross, g.same]
    })).hexdigest()


def boundary_work(g, mapping):
    groups = g.view(mapping)[0]
    work = {s: 0. for s in groups}
    for size, _, ps, cs, final in g.tensors:
        for s in {mapping[u] for u in ps | cs}:
            lp, lc = ps & groups[s], cs & groups[s]
            if lc and not lp:
                work[s] += size / g.bandwidth
            if lp and (final or not cs or cs - groups[s]):
                work[s] += size / g.bandwidth
    return work


def fluid_time(g, plan, duration, work):
    """Event jumps at task starts/finishes; at most O(tasks) event rounds.

    Aggregate fractional DDR demand above 1 slows active DDR-consuming tasks.
    Pure-compute tasks remain unaffected. No per-cycle loop.
    """
    mapping = {int(u): s for u, s in plan['node_to_subgraph'].items()}
    groups, pred, _, _ = g.view(mapping)
    seqs = plan['core_schedules']
    owner = {s: c for c, seq in enumerate(seqs) for s in seq}
    index = [0] * len(seqs)
    active, finished = {}, {}
    memory = {s: min(1., work[s]/max(duration[s], 1e-12)) for s in groups}
    t = 0.
    for _ in range(4*len(groups)+4):
        for s in list(active):
            if active[s] <= 1e-8:
                finished[s] = t
                del active[s]
                index[owner[s]] += 1
        if len(finished) == len(groups):
            return t
        releases = []
        for c, seq in enumerate(seqs):
            if index[c] >= len(seq):
                continue
            s = seq[index[c]]
            if s in active or not pred[s] <= finished.keys():
                continue
            ready = max((finished[a] + (g.cross if owner[a] != c else 0) for a in pred[s]), default=0.)
            if index[c]:
                ready = max(ready, finished[seq[index[c]-1]] + g.same)
            if ready <= t + 1e-8:
                active[s] = float(duration[s])
            else:
                releases.append(ready)
        demand = sum(memory[s] for s in active)
        rates = {s: (1/max(1., demand) if memory[s] else 1.) for s in active}
        events = [active[s]/rates[s] for s in active]
        events += [r-t for r in releases]
        if not events:
            raise ValueError('No feasible fluid event: cyclic or incomplete plan')
        dt = max(0., min(events))
        for s in active:
            active[s] -= dt*rates[s]
        t += dt
    raise RuntimeError('Fluid event bound exceeded')


class FrozenCost:
    def __init__(self, g, incumbent, result):
        self.g = copy.copy(g)
        self.g.local_observations = dict(g.local_observations)
        self.g.ratios = copy.deepcopy(g.ratios)
        self.g.region_stats = []
        self.state = state_hash(self.g)
        self.cache = {}
        base, fluid = self.components(incumbent)
        delta = max(0., fluid-base)
        self.alpha = min(2., max(0., (result['makespan']-base)/delta)) if delta > 1e-8 else 0.
        self.calibration = {'base': base, 'fluid': fluid, 'official': result['makespan'],
                            'alpha': self.alpha, 'source': 'incumbent_only'}

    def components(self, plan):
        key = canonical(plan)
        if key not in self.cache:
            mapping = {int(u): s for u, s in plan['node_to_subgraph'].items()}
            duration = self.g.costs(mapping)[0]
            base = replay(self.g, plan, duration)
            fluid = fluid_time(self.g, plan, duration, boundary_work(self.g, mapping))
            self.cache[key] = base, fluid
        return self.cache[key]

    def score(self, plan, calibrated=True):
        base, fluid = self.components(plan)
        return base + (self.alpha*max(0., fluid-base) if calibrated else 0.)

    def check(self):
        if state_hash(self.g) != self.state:
            raise RuntimeError('Frozen cost observations changed during candidate audit')
