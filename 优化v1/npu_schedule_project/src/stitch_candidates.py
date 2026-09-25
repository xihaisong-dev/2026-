"""Extra Scene A candidates taken from the other 9.25 solvers.

Each family is a structural rule. Nothing here reads a case id or a stored
score. Plans are appended after BuildAb's own keeper, so a worse plan cannot
replace a plan that already won. The official evaluator still picks the winner.
"""
from __future__ import annotations
from collections import defaultdict
import bisect

from solver import _fingerprint, _heft_plan, _plan


def _pad(plan, n):
    """A schedule that uses fewer than n cores is still a legal n-core plan."""
    if plan is None:
        return None
    schedules = plan['core_schedules']
    if len(schedules) >= n:
        return plan
    return {
        'node_to_subgraph': plan['node_to_subgraph'],
        'core_schedules': list(schedules) + [[] for _ in range(n - len(schedules))],
    }


def _try(name, builder, out, seen):
    try:
        plan = builder()
    except ValueError:
        return
    if not plan:
        return
    fp = _fingerprint(plan)
    if fp in seen:
        return
    seen.add(fp)
    out.append((name, plan))


def _weighted_window(m, n, target_groups, comm_scale):
    forward = {}
    for node in m.topo:
        forward[node] = float(m.ops[node]['cycles']) + max(
            (forward[parent] for parent in m.pred[node]), default=0.0)
    span = max(forward.values(), default=0.0)
    if not span:
        return None
    width = max(1.0, span / max(2, target_groups))
    labels = {node: int(forward[node] // width) for node in m.ids}
    groups = m.connected_groups(labels)
    return _heft_plan(m, groups, n, 1, comm_scale)


def _critical_cut(m, n, balance_fraction, comm_scale):
    if not m.ids:
        return None
    forward = {}
    for node in m.topo:
        forward[node] = float(m.ops[node]['cycles']) + max(
            (forward[parent] for parent in m.pred[node]), default=0.0)
    ordered = sorted(m.ids, key=lambda node: (forward[node], node))
    total = sum(float(m.ops[node]['cycles']) for node in ordered) or 1.0
    targets = [total * i / n for i in range(1, n)]
    cuts = []
    edge_neighbors = defaultdict(list)
    for (u, v), size in m.edge_bytes.items():
        edge_neighbors[u].append((v, size))
        edge_neighbors[v].append((u, size))
    for target in targets:
        candidates = []
        running = 0.0
        prefix = set()
        crossing = 0.0
        for index, node in enumerate(ordered[:-1]):
            for other, size in edge_neighbors[node]:
                crossing += -size if other in prefix else size
            prefix.add(node)
            running += float(m.ops[node]['cycles'])
            if abs(running - target) <= total * balance_fraction:
                candidates.append((crossing, abs(running - target), index))
        if not candidates:
            continue
        cuts.append(min(candidates)[2])
    cuts = sorted(set(cuts))
    if len(cuts) < 1:
        return None
    positions = {node: index for index, node in enumerate(ordered)}
    labels = {}
    for node in m.ids:
        position = positions[node]
        labels[node] = sum(position > cut for cut in cuts)
    groups = m.connected_groups(labels)
    return _heft_plan(m, groups, n, 1, comm_scale)


def _component_groups(m, n, group_sizes):
    comps = sorted((sorted(group) for group in m.components), key=lambda group: group[0])
    plans = []
    for gsize in group_sizes:
        if gsize > len(comps):
            continue
        groups = []
        for start in range(0, len(comps), gsize):
            members = []
            for comp in comps[start:start + gsize]:
                members.extend(comp)
            groups.append(sorted(members))
        duration = [sum(int(m.ops[node]['cycles']) for node in group) for group in groups]
        order = sorted(range(len(groups)), key=lambda index: (-duration[index], groups[index][0]))
        loads = [0] * n
        assignment = {}
        for index in order:
            core = min(range(n), key=lambda slot: (loads[slot], slot))
            assignment[index] = core
            loads[core] += duration[index]
        emit = sorted(range(len(groups)), key=lambda index: groups[index][0])
        plans.append(('component_group%d' % gsize, _plan(groups, assignment, emit, n, False)))
    return plans


def _pipevec_merge(m, n):
    groups = [sorted(group) for group in m.components]
    if len(groups) < 2:
        return None
    loads_of = []
    for group in groups:
        vector = m.cost_vector(group)
        loads_of.append(0.5 * max(vector.values()) + 0.5 * sum(vector.values()))
    core_load = [0.0] * n
    assignment = {}
    for index in sorted(range(len(groups)), key=lambda index: (-loads_of[index], groups[index][0])):
        core = min(range(n), key=lambda slot: (core_load[slot], slot))
        assignment[index] = core
        core_load[core] += loads_of[index]
    order = sorted(range(len(groups)), key=lambda index: groups[index][0])
    return _plan(groups, assignment, order, n, False)


def _work_by_depth(m):
    max_depth = max(m.depth.values()) if m.ids else 0
    work = [0.0] * (max_depth + 1)
    for node in m.ids:
        work[m.depth[node]] += max(1.0, float(m.ops[node]['cycles']))
    return work


def _uniform_stage_labels(m, num_stages):
    work = _work_by_depth(m)
    total = sum(work)
    if total <= 0 or num_stages <= 1:
        return {node: 0 for node in m.ids}
    cum = []
    acc = 0.0
    for item in work:
        acc += item
        cum.append(acc)
    thresholds = []
    for index in range(1, num_stages):
        depth = bisect.bisect_left(cum, total * index / num_stages)
        thresholds.append(depth + 1)
    thresholds = sorted(set(item for item in thresholds if 1 <= item <= len(work) - 1))
    return {node: bisect.bisect_right(thresholds, m.depth[node]) for node in m.ids}


def _cut_bytes_by_threshold(m):
    max_depth = max(m.depth.values()) if m.ids else 0
    diff = [0.0] * (max_depth + 2)
    for (source, target), size in m.edge_bytes.items():
        left, right = m.depth[source], m.depth[target]
        if right > left:
            diff[left + 1] += size
            diff[right + 1] -= size
    cut = [0.0] * (max_depth + 2)
    running = 0.0
    for depth in range(1, max_depth + 1):
        running += diff[depth]
        cut[depth] = running
    return cut, max_depth


def _commaware_stage_labels(m, num_stages, snap=0.30):
    work = _work_by_depth(m)
    total = sum(work)
    max_depth = len(work) - 1
    if total <= 0 or num_stages <= 1 or max_depth <= 0:
        return {node: 0 for node in m.ids}
    cut, _ = _cut_bytes_by_threshold(m)
    cum = []
    acc = 0.0
    for item in work:
        acc += item
        cum.append(acc)
    band = max(1, max_depth // num_stages)
    radius = max(1, int(band * snap))
    thresholds = []
    for index in range(1, num_stages):
        center = bisect.bisect_left(cum, total * index / num_stages) + 1
        lo = max(1, center - radius)
        hi = min(max_depth, center + radius)
        best_t, best_key = center, None
        for depth in range(lo, hi + 1):
            key = (cut[depth], abs(depth - center))
            if best_key is None or key < best_key:
                best_key, best_t = key, depth
        thresholds.append(best_t)
    thresholds = sorted(set(item for item in thresholds if 1 <= item <= max_depth))
    return {node: bisect.bisect_right(thresholds, m.depth[node]) for node in m.ids}


def _stage_plan(m, n, stages, cores, kind):
    if kind == 'U':
        labels = _uniform_stage_labels(m, stages)
    else:
        labels = _commaware_stage_labels(m, stages)
    groups = m.connected_groups(labels)
    return _pad(_heft_plan(m, groups, cores, 1, 1.0), n)


def _membatch(m, graph, n, cap_frac=0.70):
    managed = {
        tensor['id']: (tensor.get('pos'), tensor['size'])
        for tensor in graph['tensors'] if tensor.get('pos') in ('L1', 'UB')
    }
    op_ids = set(m.ids)
    op_tids = defaultdict(set)
    for edge in graph['edges']:
        source, target = edge['source'], edge['target']
        if source in op_ids and target in managed:
            op_tids[source].add(target)
        elif target in op_ids and source in managed:
            op_tids[target].add(source)
    comp_tids = []
    for comp in m.components:
        touched = set()
        for node in comp:
            touched |= op_tids.get(node, ())
        comp_tids.append(touched)
    from solver import _component_plan
    merged = _component_plan(m, n, 'pipe', True)
    by_core = defaultdict(list)
    for index, comp in enumerate(m.components):
        core = merged['node_to_subgraph'][str(comp[0])]
        by_core[core].append(index)
    l1_lim, ub_lim = cap_frac * 524288, cap_frac * 131072
    groups, assignment, order = [], {}, []

    def flush(ops, core):
        if not ops:
            return
        gid = len(groups)
        groups.append(sorted(ops))
        assignment[gid] = core
        order.append(gid)

    for core in range(n):
        batch, seen, l1, ub = [], set(), 0.0, 0.0
        for index in sorted(by_core[core], key=lambda item: min(m.components[item])):
            fresh = comp_tids[index] - seen
            add_l1 = sum(managed[tensor][1] for tensor in fresh if managed[tensor][0] == 'L1')
            add_ub = sum(managed[tensor][1] for tensor in fresh if managed[tensor][0] == 'UB')
            if batch and (l1 + add_l1 > l1_lim or ub + add_ub > ub_lim):
                flush(batch, core)
                batch, seen, l1, ub = [], set(), 0.0, 0.0
                fresh = comp_tids[index]
                add_l1 = sum(managed[tensor][1] for tensor in fresh if managed[tensor][0] == 'L1')
                add_ub = sum(managed[tensor][1] for tensor in fresh if managed[tensor][0] == 'UB')
            batch.extend(m.components[index])
            seen |= comp_tids[index]
            l1 += add_l1
            ub += add_ub
        flush(batch, core)
    if len(groups) < 2:
        return None
    return _plan(groups, assignment, order, n, False)


def _depth_window(m, n, width):
    labels = {node: m.depth[node] // width for node in m.ids}
    groups = m.connected_groups(labels)
    if len(groups) < 2:
        return None
    return _heft_plan(m, groups, n, 1, 1.0)


def stitch_plans(m, n, graph):
    """Return extra plans. Callers dedup against the plans they already keep."""
    if n != 5 or not m.ids:
        return []
    out, seen = [], set()
    nodes = len(m.ids)
    components = len(m.components)
    depth = max(m.depth.values()) if m.depth else 0

    # Critical-work windows and communication-aware cuts. Skipped on the
    # largest graphs, where one extra partition is too expensive to evaluate.
    if nodes <= 12000:
        for target, scale in ((20, 1.0), (15, 0.65), (10, 0.35)):
            _try('weighted_window_%d_s%s' % (target, scale),
                 lambda target=target, scale=scale: _weighted_window(m, n, target, scale),
                 out, seen)
        for balance, scale in ((0.16, 1.0), (0.06, 0.35)):
            _try('critical_cut_b%s_s%s' % (balance, scale),
                 lambda balance=balance, scale=scale: _critical_cut(m, n, balance, scale),
                 out, seen)
        for width in (5, 7, 14, 23):
            if depth + 1 < width * 2:
                continue
            _try('win_w%d' % width,
                 lambda width=width: _depth_window(m, n, width),
                 out, seen)

    # Coarse work bands, including a 4-core placement padded out to 5 cores.
    if nodes <= 8000 and depth >= 8:
        _try('stageU4_k5', lambda: _stage_plan(m, n, 4, 5, 'U'), out, seen)
        _try('stageC5_k4', lambda: _stage_plan(m, n, 5, 4, 'C'), out, seen)
        _try('stageU12_k5', lambda: _stage_plan(m, n, 12, 5, 'U'), out, seen)

    # Pack consecutive weak components. Only the sizes that beat a published
    # baseline are emitted, and only while the component count stays modest.
    if 3 <= components <= 200:
        for name, plan in _component_groups(m, n, (3, 4, 5, 6, 8)):
            _try(name, lambda plan=plan: plan, out, seen)
    if 2 <= components <= 200:
        _try('pipevec_merge', lambda: _pipevec_merge(m, n), out, seen)
        if nodes <= 8000:
            _try('membatch_70', lambda: _membatch(m, graph, n, 0.70), out, seen)
    return out
