# Adapted from the user-supplied npu_schedule_project/src/solver.py.
# Archive SHA256: 48aaca6e46f9ddc2d0e846e303dfe841bec2f8f0ab12afeb0898b7b7805d9e8f
# Structure-generation logic is attributed to that package, not claimed as original.
# Integration uses our fixed-config official A evaluator and bounded search budget.
"""Deterministic graph-structure-aware NPU schedule candidate generator.

Only the two contest plan keys are returned.  This module estimates costs solely
for proposing candidates; all reported makespans must come from the unmodified
contest evaluator.  No learned model, case number, or precomputed answer is used.
"""
from __future__ import annotations
from collections import defaultdict, deque
import heapq
import math

COPY_TYPES = {"COPY_IN", "COPY_OUT"}
PIPES = ("PIPE_M", "PIPE_V", "PIPE_MTE2", "PIPE_MTE3")


class GraphModel:
    def __init__(self, graph, settings, waits):
        self.bandwidth = settings["bandwidth"]
        self.cross_wait = waits["task_cross_core_wait_cycles"]
        self.same_wait = waits["task_same_core_wait_cycles"]
        self.graph = graph
        all_ops = {o['id']: o for o in graph['ops']}
        self.ops = {u: o for u, o in all_ops.items() if o['op'] not in COPY_TYPES}
        self.ids = sorted(self.ops)
        self.tensors = {t['id']: t for t in graph['tensors']}
        prod, cons = defaultdict(set), defaultdict(set)
        adj = {u: {} for u in all_ops}
        self.inputs, self.outputs = defaultdict(set), defaultdict(set)
        for e in graph['edges']:
            a, b = e['source'], e['target']
            if a in all_ops and b in all_ops:
                adj[a][b] = 0
            elif a in all_ops:
                prod[b].add(a)
                self.outputs[a].add(b)
            else:
                cons[a].add(b)
                self.inputs[b].add(a)
        for t, pp in prod.items():
            for p in pp:
                for c in cons[t]:
                    adj[p][c] = adj[p].get(c, 0) + self.tensors[t]['size']
        self.pred = {u: set() for u in self.ids}
        self.succ = {u: set() for u in self.ids}
        self.edge_bytes = {}
        for u in self.ids:
            stack = list(adj[u].items())
            visited = set()
            while stack:
                v, size = stack.pop()
                if v in self.ops:
                    self.succ[u].add(v)
                    self.pred[v].add(u)
                    self.edge_bytes[u, v] = max(size, self.edge_bytes.get((u,v),0))
                elif v not in visited:
                    visited.add(v)
                    stack.extend((w, max(size, s)) for w, s in adj[v].items())
        self.depth = {}
        indeg = {u: len(self.pred[u]) for u in self.ids}
        ready = [u for u in self.ids if not indeg[u]]
        heapq.heapify(ready)
        self.topo = []
        while ready:
            u = heapq.heappop(ready)
            self.topo.append(u)
            self.depth[u] = max((self.depth[v] + 1 for v in self.pred[u]), default=0)
            for v in sorted(self.succ[u]):
                indeg[v] -= 1
                if not indeg[v]: heapq.heappush(ready, v)
        if len(self.topo) != len(self.ids):
            raise ValueError('compute dependency graph is cyclic')
        self.components = self.connected_groups({u: 0 for u in self.ids})
        # Original DDR input identities associated with each compute consumer.
        self.ddr_inputs = defaultdict(set)
        for t, pp in prod.items():
            for p in pp:
                if all_ops[p]['op'] == 'COPY_IN':
                    external = {a for a in self.inputs[p] if self.tensors[a]['pos']=='DDR'}
                    for c in cons[t]:
                        if c in self.ops: self.ddr_inputs[c].update(external)

    def connected_groups(self, labels):
        """Weak components restricted to one monotone depth window."""
        groups, seen = [], set()
        for u in self.ids:
            if u in seen: continue
            stack, group = [u], []
            seen.add(u)
            while stack:
                v = stack.pop(); group.append(v)
                for w in sorted(self.pred[v] | self.succ[v], reverse=True):
                    if w not in seen and labels[w] == labels[v]:
                        seen.add(w); stack.append(w)
            groups.append(sorted(group))
        return groups

    def chain_groups(self):
        """Fuse maximal edges having outdegree(source)=indegree(target)=1."""
        groups, seen = [], set()
        for u in self.topo:
            if u in seen: continue
            group, v = [], u
            while True:
                seen.add(v); group.append(v)
                if len(self.succ[v]) != 1: break
                w = next(iter(self.succ[v]))
                if len(self.pred[w]) != 1 or w in seen: break
                v = w
            groups.append(group)
        return groups

    def cost_vector(self, members):
        costs = dict.fromkeys(PIPES, 0.)
        for u in members:
            costs[self.ops[u]['pipe']] += float(self.ops[u]['cycles'])
        return costs

    def group_inputs(self, members):
        return set().union(*(self.ddr_inputs[u] for u in members)) if members else set()


def _plan(groups, assignment, order, n, merge=False):
    schedules = [[] for _ in range(n)]
    mapping = {}
    for gid in order:
        c = assignment[gid]
        sg = c if merge else gid
        if not schedules[c] or schedules[c][-1] != sg: schedules[c].append(sg)
        for u in groups[gid]: mapping[str(u)] = sg
    return {'node_to_subgraph': mapping, 'core_schedules': schedules}


def _component_plan(m, n, mode='lpt', merge=True, order_mode='id'):
    groups = m.components
    costs = [m.cost_vector(g) for g in groups]
    scalar = [max(c.values()) + .08 * sum(c.values()) for c in costs]
    order = sorted(range(len(groups)), key=lambda j: (-scalar[j], min(groups[j])))
    loads = [dict.fromkeys(PIPES,0.) for _ in range(n)]
    assignment = {}
    for j in order:
        if mode=='round_robin':
            c = j % n
        elif mode=='lpt':
            c = min(range(n), key=lambda k:(sum(loads[k].values()), k))
        else:
            c = min(range(n), key=lambda k:(max(loads[k][p]+costs[j][p] for p in PIPES), sum(loads[k].values()), k))
        assignment[j] = c
        for p in PIPES: loads[c][p] += costs[j][p]
    if order_mode=='id':
        order = sorted(range(len(groups)), key=lambda j: min(groups[j]))
    elif order_mode=='reuse':
        inputs = [m.group_inputs(g) for g in groups]
        frequency = defaultdict(int)
        for ts in inputs:
            for t in ts: frequency[t] += 1
        # Frequent source tensors are processed together.  Deterministic tie breaks.
        key = {j: tuple(sorted(inputs[j],key=lambda t:(-frequency[t],t))) for j in range(len(groups))}
        order = sorted(range(len(groups)), key=lambda j:(key[j], min(groups[j])))
    return _plan(groups, assignment, order, n, merge)


def _component_batch_plan(m, n, max_compute_ops=256):
    """Bound task size without cutting any weak component.

    A large component remains intact even when it exceeds the target batch size.
    The official memory allocator enforces actual byte capacities; the node budget
    is a task-granularity heuristic and is not a memory-capacity surrogate.
    """
    merged = _component_plan(m, n, 'pipe', True)
    by_core = defaultdict(list)
    for component in m.components:
        core = merged['node_to_subgraph'][str(component[0])]
        by_core[core].append(component)
    groups, assignment, order = [], {}, []
    def append_batch(members, core):
        gid = len(groups)
        groups.append(members)
        assignment[gid] = core
        order.append(gid)
    for core in range(n):
        batch = []
        for component in sorted(by_core[core], key=min):
            if batch and len(batch)+len(component)>max_compute_ops:
                append_batch(batch, core)
                batch = []
            batch.extend(component)
        if batch: append_batch(batch, core)
    return _plan(groups, assignment, order, n)


def _heft_plan(m, groups, n, problem, comm_scale=1.):
    """Critical-rank list scheduling with estimated locality-aware finish times.

    Global ready-list order is topological. Appending groups to core schedules in
    that order cannot introduce a task-order cycle. Scene B still requires the
    official global operation/FIFO/memory check.
    """
    belongs = {u:j for j,g in enumerate(groups) for u in g}
    pred = [set() for _ in groups]
    succ = [set() for _ in groups]
    edge = defaultdict(float)
    for u in m.ids:
        j = belongs[u]
        for v in m.succ[u]:
            k = belongs[v]
            if j != k:
                pred[k].add(j); succ[j].add(k)
                edge[j,k] += m.edge_bytes.get((u,v),0)
    # A topological ordering of original nodes induces a topological group order
    # for convex windows and maximal nonbranching chains.
    indeg = [len(p) for p in pred]
    q = [j for j in range(len(groups)) if not indeg[j]]
    heapq.heapify(q); topo=[]
    while q:
        j=heapq.heappop(q);topo.append(j)
        for k in sorted(succ[j]):
            indeg[k]-=1
            if not indeg[k]:heapq.heappush(q,k)
    if len(topo)!=len(groups):raise ValueError('nonconvex grouping')
    vectors = [m.cost_vector(g) for g in groups]
    duration = [max(v.values())+.08*sum(v.values()) for v in vectors]
    rank = {}
    for j in reversed(topo):
        rank[j] = duration[j]+max((rank[k] for k in succ[j]),default=0)
    indeg = [len(p) for p in pred]
    ready = [(-rank[j],j) for j in topo if not indeg[j]]
    heapq.heapify(ready)
    core_time = [0.]*n
    assignment,finish,order = {},{},[]
    cross_delay = float(m.cross_wait)
    same_delay = float(m.same_wait)
    while ready:
        _,j=heapq.heappop(ready)
        choices=[]
        for c in range(n):
            release = core_time[c] + (same_delay if core_time[c] else 0.)
            transfer=0.
            for p in pred[j]:
                cross = assignment[p] != c
                wait = (cross_delay if cross else same_delay)
                traffic = (2.*edge[p,j]/m.bandwidth) if cross or problem==1 else 0.
                release=max(release,finish[p]+comm_scale*(wait+traffic))
                transfer+=traffic
            choices.append((release+duration[j],transfer,core_time[c],c))
        done,_,_,c=min(choices)
        assignment[j]=c;finish[j]=done;core_time[c]=done;order.append(j)
        for k in sorted(succ[j]):
            indeg[k]-=1
            if not indeg[k]:heapq.heappush(ready,(-rank[k],k))
    return _plan(groups,assignment,order,n)


def canonical_key(plan):
    """Ignore subgraph labels, but preserve core identities and execution order."""
    rename = {s: i for i, s in enumerate(s for seq in plan['core_schedules'] for s in seq)}
    return (tuple(sorted((int(u), rename[s]) for u, s in plan['node_to_subgraph'].items())),
            tuple(tuple(rename[s] for s in seq) for seq in plan['core_schedules']))


def initial_candidates(raw, settings, waits, cores, families):
    """Static bounded seeds; no evaluator calls or observed-cost state used here.

    Combined priority covers a whole-component, batch and depth alternative
    before secondary variants. Structural gates follow the supplied package.
    Caller limits accepted unique seeds and reserves four base grain attempts.
    """
    families = set(families)
    if families - {'components', 'batches', 'depth'}:
        raise ValueError('Unknown structural family')
    m = GraphModel(raw, settings, waits)
    total = sum(o['cycles'] for o in m.ops.values())
    largest = max((sum(m.ops[u]['cycles'] for u in g) for g in m.components), default=0)
    dominant = largest > total / cores * 1.15
    batch_ok = len(m.components) >= 2 * cores and not dominant
    info = {'components': len(m.components), 'largest_component_cycles': largest,
            'total_cycles': total, 'dominant_component': dominant, 'batch_eligible': batch_ok,
            'generation_state': 'fixed raw graph and config; no observations', 'generated': []}
    choices = []
    def add(family, name, builder):
        if family in families:
            choices.append((name, builder))
    add('components', 'component_lpt', lambda: _component_plan(m, cores, 'lpt', True))
    if batch_ok:
        add('batches', 'component_batches256', lambda: _component_batch_plan(m, cores, 256))
    def window(width):
        groups = m.connected_groups({u: m.depth[u] // width for u in m.ids})
        return _heft_plan(m, groups, cores, 1)
    if dominant:
        add('depth', 'depth8', lambda: window(8))
    add('components', 'component_pipe', lambda: _component_plan(m, cores, 'pipe', True))
    if dominant:
        add('depth', 'depth16', lambda: window(16))
    add('components', 'component_round_robin', lambda: _component_plan(m, cores, 'round_robin', True))
    if dominant:
        add('depth', 'depth4', lambda: window(4))
    plans = [(name, builder()) for name, builder in choices]
    info['generated'] = [name for name, _ in plans]
    return plans, info


def guarded_component_candidate(raw, settings, waits, cores, *, max_candidates=1, ranking="static"):
    """One statically ranked whole-component seed; no simulator or case-ID routing.

    Union footprint is a conservative routing hint, not a live-memory bound.
    If *every* component already has a footprint exceeding private capacity,
    avoid packing multiple such components into a large fused task.
    """
    if ranking not in ("static", "local"):
        raise ValueError("Unknown component ranking")
    if max_candidates not in (1, 2):
        raise ValueError("Component candidate limit must be 1 or 2")
    m = GraphModel(raw, settings, waits)
    vectors = [m.cost_vector(g) for g in m.components]
    weights = [max(v.values()) for v in vectors]
    total = sum(weights)
    over_capacity = []
    for group in m.components:
        tensors = set().union(*(m.inputs[u] | m.outputs[u] for u in group))
        footprint = {pos: sum(m.tensors[t]['size'] for t in tensors
                              if m.tensors[t]['pos'] == pos)
                     for pos in settings['capacity']}
        over_capacity.append(any(footprint[pos] > cap for pos, cap in settings['capacity'].items()))
    info = dict(components=len(m.components), generation_state='fixed raw graph and config',
                component_work_sum=total, largest_component_work=max(weights, default=0),
                over_capacity_components=sum(over_capacity), footprint_semantics='union, not live peak',
                ranked=[], generated=[])
    if cores <= 1 or len(m.components) < cores:
        info['gate'] = 'insufficient_independent_components'
        return [], info
    if max(weights, default=0) * cores > total:
        info['gate'] = 'dominant_component'
        return [], info
    if over_capacity and all(over_capacity):
        info['gate'] = 'all_components_have_large_union_footprint'
        return [], info
    info['gate'] = 'eligible'
    ranked = []
    seen = set()
    for mode in ['lpt', 'pipe', 'round_robin']:
        plan = _component_plan(m, cores, mode, True)
        key = canonical_key(plan)
        if key in seen:
            continue
        seen.add(key)
        loads = [dict.fromkeys(PIPES, 0.) for _ in range(cores)]
        inputs = [set() for _ in range(cores)]
        for u in m.ids:
            core = plan['node_to_subgraph'][str(u)]
            loads[core][m.ops[u]['pipe']] += float(m.ops[u]['cycles'])
            inputs[core].update(m.ddr_inputs[u])
        compute_lb = max((max(v.values()) for v in loads), default=0.)
        input_bytes = sum(m.tensors[t]['size'] for ids in inputs for t in ids)
        score = (compute_lb, input_bytes, max(sum(v.values()) for v in loads))
        record = dict(candidate='component_' + mode, compute_lower_bound=compute_lb,
                      input_read_bytes=input_bytes, max_core_work=score[2])
        ranked.append((score, len(ranked), record, plan))
    ranked.sort(key=lambda x: (x[0], x[1]))
    if ranking == 'local':
        # Independent local preparation only; no global candidate result or
        # online observation is available to this fixed-state ranker.
        from q1_experimental import CostGraph
        from q1_local_rank import LocalRank
        ranker = LocalRank(raw, CostGraph(raw, settings, waits, False))
        for item in ranked:
            value, _, _ = ranker.score(item[3])
            item[2]['local_prediction'] = value
        ranked.sort(key=lambda x: (x[2]['local_prediction'], x[1]))
        info['ranking'] = 'local_task_profiles_frozen_state'
        info['local_preparation'] = ranker.stats()
        assert info['local_preparation']['global_evaluations'] == 0
    info['ranked'] = [x[2] for x in ranked]
    winner = ranked[0]
    info['selected_compute_lower_bound'] = winner[2]['compute_lower_bound']
    selected = [winner]
    if max_candidates == 2:
        # Different grouping, not just a permutation of identical core labels.
        def grouping(plan):
            groups = defaultdict(list)
            for u, sid in plan['node_to_subgraph'].items():
                groups[sid].append(int(u))
            return tuple(sorted(tuple(sorted(nodes)) for nodes in groups.values()))
        first_groups = grouping(winner[3])
        alternative = next((x for x in ranked[1:] if grouping(x[3]) != first_groups), None)
        if alternative is not None:
            selected.append(alternative)
        info['followup_diversity'] = 'different node grouping ignoring core labels'
        info['candidate_compute_bounds'] = {x[2]['candidate']: x[2]['compute_lower_bound'] for x in selected}
    info['generated'] = [x[2]['candidate'] for x in selected]
    return [(x[2]['candidate'], x[3]) for x in selected], info
