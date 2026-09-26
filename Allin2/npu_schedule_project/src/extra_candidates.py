"""Extra problem-1 schedules appended after the Allin candidate cap.

Structural families, chosen from the graph rather than the case id:

- Variable-width depth windows plus the Kios HEFT/PEFT list scheduler.
  Every edge on these DAGs increases depth, so a depth-band label stays convex.
- Contiguous topological pipeline segments (DSC-style). A contiguous slice of
  ``m.topo`` has only forward edges, so the quotient is a chain.
- Light-cut depth bands: keep growing a band across a heavy depth boundary and
  cut only on a light boundary. Same convexity argument as the depth windows.

``heft2`` matches the published list scheduler, including its append-style
release. ``peftins`` is PEFT processor selection with a real idle-slot
insertion; the slot must finish a same-core wait before the next task, so
later tasks already on that core are not pushed.

The ``kios_*`` and ``niu_*`` plans are the Scene A families from the 9.24
Kios ``solver_opt`` and NiuDs adaptive window. They are appended here and
are not truncated to 12, so they cannot evict an Allin or variable-window
winner. Graphs above 12,000 nodes skip those two families: those official
evaluations already sit near or past the 600-second target. Official
makespan still chooses. A new plan is added only when its fingerprint is new.
"""
from __future__ import annotations

from collections import defaultdict
import heapq

SAME_CORE_WAIT = 100.0
CROSS_CORE_WAIT = 1000.0
DDR_BANDWIDTH = 60.0

VW_CONFIGS = (
    (16, 8, 15), (16, 8, 8), (24, 8, 15), (24, 8, 25),
    (24, 10, 15), (24, 4, 15), (20, 6, 15), (32, 8, 15),
)
# Width triple plus the maximum outgoing bytes at which a wide level is still
# split. Heavier cuts keep the coarse window.
CAV_CONFIGS = (
    (16, 8, 15, 65536),
    (24, 8, 15, 262144),
)
# min span, max span, incoming-byte limit that still counts as a light cut.
LIGHT_CONFIGS = (
    (4, 16, 65536),
    (8, 32, 262144),
)
PIPE_SCALES = (0.5, 1.0, 2.0)
MAX_GROUPS = 2000
PEFT_GROUP_CAP = 500


def _find_slot(busy, release, dur, gap):
    """Earliest [start, finish) that fits in an idle gap, with `gap` on both sides."""
    lo = 0.0
    for start, end in busy:
        cand = max(release, lo)
        if cand + dur <= start - gap - 1e-9:
            return cand, cand + dur
        lo = end + gap
    cand = max(release, lo)
    return cand, cand + dur


def _group_graph(m, groups):
    belongs = {u: j for j, group in enumerate(groups) for u in group}
    pred = [set() for _ in groups]
    succ = [set() for _ in groups]
    edge = defaultdict(float)
    for u in m.ids:
        j = belongs[u]
        for v in m.succ[u]:
            k = belongs[v]
            if j != k:
                pred[k].add(j)
                succ[j].add(k)
                edge[j, k] += m.edge_bytes.get((u, v), 0)
    return pred, succ, edge


def _topo_groups(pred, succ, groups):
    indeg = [len(p) for p in pred]
    ready = [j for j in range(len(groups)) if not indeg[j]]
    heapq.heapify(ready)
    topo = []
    while ready:
        j = heapq.heappop(ready)
        topo.append(j)
        for k in sorted(succ[j]):
            indeg[k] -= 1
            if not indeg[k]:
                heapq.heappush(ready, k)
    if len(topo) != len(groups):
        raise ValueError('nonconvex grouping')
    return topo


def _durations(m, groups, pred, edge, include_traffic):
    out = []
    for j, group in enumerate(groups):
        vector = m.cost_vector(group)
        compute = max(vector.values()) + 0.08 * sum(vector.values())
        traffic = 0.0
        if include_traffic:
            traffic = 2.0 * sum(edge[p, j] for p in pred[j]) / DDR_BANDWIDTH
        out.append(compute + traffic)
    return out


def _plan_sorted(groups, assignment, start, n):
    schedules = [[] for _ in range(n)]
    mapping = {}
    order = sorted(range(len(groups)), key=lambda j: (assignment[j], start[j], j))
    for j in order:
        schedules[assignment[j]].append(j)
        for u in groups[j]:
            mapping[str(u)] = j
    return {'node_to_subgraph': mapping, 'core_schedules': schedules}


def _plan_rr(groups, n):
    schedules = [[] for _ in range(n)]
    mapping = {}
    for gid in range(len(groups)):
        core = gid % n
        schedules[core].append(gid)
        for u in groups[gid]:
            mapping[str(u)] = gid
    return {'node_to_subgraph': mapping, 'core_schedules': schedules}


def _heft2(m, groups, n):
    """Kios list scheduler: PEFT-style cross-core rank, append-style release."""
    pred, succ, edge = _group_graph(m, groups)
    topo = _topo_groups(pred, succ, groups)
    duration = _durations(m, groups, pred, edge, True)
    insert = len(groups) <= PEFT_GROUP_CAP
    rank = {}
    for j in reversed(topo):
        best = 0.0
        for k in succ[j]:
            extra = CROSS_CORE_WAIT + 2.0 * edge[j, k] / DDR_BANDWIDTH
            best = max(best, rank[k] + extra)
        rank[j] = duration[j] + best
    indeg = [len(p) for p in pred]
    ready = [(-rank[j], j) for j in topo if not indeg[j]]
    heapq.heapify(ready)
    busy, core_end = [[] for _ in range(n)], [0.0] * n
    assignment, start, finish = {}, {}, {}
    while ready:
        _, j = heapq.heappop(ready)
        dur = duration[j]
        best = None
        for core in range(n):
            release = core_end[core] + SAME_CORE_WAIT if busy[core] else 0.0
            transfer = 0.0
            for p in pred[j]:
                cross = assignment[p] != core
                wait = CROSS_CORE_WAIT if cross else SAME_CORE_WAIT
                traffic = (2.0 * edge[p, j] / DDR_BANDWIDTH) if cross else 0.0
                release = max(release, finish[p] + wait + traffic)
                transfer += traffic
            if insert:
                st, en = _find_slot(busy[core], release, dur, SAME_CORE_WAIT)
            else:
                st = max(release, core_end[core])
                en = st + dur
            key = (en, transfer, core_end[core], core)
            if best is None or key < best[0]:
                best = (key, core, st, en)
        _, core, st, en = best
        assignment[j] = core
        start[j], finish[j] = st, en
        busy[core].append((st, en))
        busy[core].sort()
        core_end[core] = max(core_end[core], en)
        for k in sorted(succ[j]):
            indeg[k] -= 1
            if not indeg[k]:
                heapq.heappush(ready, (-rank[k], k))
    return _plan_sorted(groups, assignment, start, n)


def _peft_insert(m, groups, n):
    """PEFT optimistic-cost selection with idle-slot insertion.

    Duration is compute only. Cross-task bytes are charged on every predecessor
    edge, including a same-core predecessor, because Scene A inserts a DDR copy
    at every task boundary. Insertion is skipped once the group count makes the
    slot scan the expensive part; those partitions already have an append PEFT
    in the baseline set.
    """
    if len(groups) > PEFT_GROUP_CAP:
        return None
    pred, succ, edge = _group_graph(m, groups)
    topo = _topo_groups(pred, succ, groups)
    duration = _durations(m, groups, pred, edge, False)
    oct_table = [[0.0] * n for _ in groups]
    for j in reversed(topo):
        if not succ[j]:
            continue
        for core in range(n):
            optimistic = 0.0
            for k in succ[j]:
                byte = edge[j, k]
                best = None
                for dest in range(n):
                    cross = core != dest
                    wait = CROSS_CORE_WAIT if cross else SAME_CORE_WAIT
                    traffic = 2.0 * byte / DDR_BANDWIDTH
                    cost = oct_table[k][dest] + duration[k] + wait + traffic
                    if best is None or cost < best:
                        best = cost
                if best > optimistic:
                    optimistic = best
            oct_table[j][core] = optimistic
    rank = {j: sum(oct_table[j]) / n for j in topo}
    indeg = [len(p) for p in pred]
    ready = [(-rank[j], j) for j in topo if not indeg[j]]
    heapq.heapify(ready)
    busy, core_end = [[] for _ in range(n)], [0.0] * n
    assignment, start, finish = {}, {}, {}
    while ready:
        _, j = heapq.heappop(ready)
        dur = duration[j]
        best = None
        for core in range(n):
            release = 0.0
            transfer = 0.0
            for p in pred[j]:
                cross = assignment[p] != core
                wait = CROSS_CORE_WAIT if cross else SAME_CORE_WAIT
                traffic = 2.0 * edge[p, j] / DDR_BANDWIDTH
                release = max(release, finish[p] + wait + traffic)
                transfer += traffic
            st, en = _find_slot(busy[core], release, dur, SAME_CORE_WAIT)
            key = (en + oct_table[j][core], en, transfer, core)
            if best is None or key < best[0]:
                best = (key, core, st, en)
        _, core, st, en = best
        assignment[j] = core
        start[j], finish[j] = st, en
        busy[core].append((st, en))
        busy[core].sort()
        core_end[core] = max(core_end[core], en)
        for k in sorted(succ[j]):
            indeg[k] -= 1
            if not indeg[k]:
                heapq.heappush(ready, (-rank[k], k))
    return _plan_sorted(groups, assignment, start, n)


def _usable(m, groups):
    if not groups or not 2 <= len(groups) <= MAX_GROUPS:
        return False
    covered = [u for group in groups for u in group]
    return len(covered) == len(set(covered)) == len(m.ids)


def _dominant(m, n):
    total = sum(float(m.ops[u]['cycles']) for u in m.ids)
    if total <= 0:
        return False
    limit = total / n * 1.15
    return any(sum(float(m.ops[u]['cycles']) for u in group) > limit for group in m.components)


def _level_widths(m):
    out = defaultdict(int)
    for u in m.ids:
        out[m.depth[u]] += 1
    return out


def _window_labels(m, narrow_w, wide_w, wide_thresh, byte_cap=None):
    depth_max = max(m.depth.values(), default=0)
    width = _level_widths(m)
    cuts = None
    if byte_cap is not None:
        cuts = defaultdict(float)
        for (u, _v), size in m.edge_bytes.items():
            cuts[m.depth[u]] += size
    labels, start = {}, 0
    for depth in range(depth_max + 1):
        if byte_cap is None:
            fine = width.get(depth, 0) >= wide_thresh
        else:
            fine = width.get(depth, 0) >= wide_thresh and cuts.get(depth, 0.0) <= byte_cap
        limit = wide_w if fine else narrow_w
        if depth - start >= limit:
            start = depth
        labels[depth] = start
    return labels


def _groups_from_depth_labels(m, labels_by_depth):
    labels = {u: labels_by_depth[m.depth[u]] for u in m.ids}
    return [group for group in m.connected_groups(labels) if group]


def _pipeline_groups(m, n, seg_scale):
    total = sum(float(m.ops[u]['cycles']) for u in m.topo)
    if total <= 0:
        return None
    target = max(1.0, total / max(1, n) * float(seg_scale))
    groups, members, acc = [], [], 0.0
    for u in m.topo:
        members.append(u)
        acc += float(m.ops[u]['cycles'])
        if acc >= target and members:
            groups.append(list(members))
            members = []
            acc = 0.0
    if members:
        groups.append(list(members))
    if not _usable(m, groups):
        return None
    return groups


def _lightcut_groups(m, min_span, max_span, light_bytes):
    present = sorted({m.depth[u] for u in m.ids})
    if len(present) < 2:
        return None
    incoming = defaultdict(float)
    for (_u, v), size in m.edge_bytes.items():
        incoming[m.depth[v]] += size
    labels, start = {}, present[0]
    for index, depth in enumerate(present):
        span = depth - start
        heavy_cut = incoming[depth] > light_bytes
        if index and (span >= max_span or (span >= min_span and not heavy_cut)):
            start = depth
        labels[depth] = start
    groups = _groups_from_depth_labels(m, labels)
    if not _usable(m, groups):
        return None
    return groups


def _try_plan(builder, m, groups, n):
    try:
        return builder(m, groups, n)
    except ValueError:
        return None


def _kios_pipe_vector(m, n):
    """Pipe-normalized LPT over whole weak components. One task per core."""
    from solver import PIPES, _plan
    groups = m.components
    if not _usable(m, groups):
        return None
    costs = [m.cost_vector(g) for g in groups]
    total_pipe = dict.fromkeys(PIPES, 0.0)
    for cost in costs:
        for pipe in PIPES:
            total_pipe[pipe] += cost[pipe]
    norm = {pipe: (total_pipe[pipe] if total_pipe[pipe] > 0 else 1.0) for pipe in PIPES}
    scalar = [max(cost.values()) + 0.08 * sum(cost.values()) for cost in costs]
    order = sorted(range(len(groups)), key=lambda j: (-scalar[j], min(groups[j])))
    loads = [dict.fromkeys(PIPES, 0.0) for _ in range(n)]
    assignment = {}
    for j in order:
        def core_key(core, j=j):
            added = {pipe: loads[core][pipe] + costs[j][pipe] for pipe in PIPES}
            nmax = max(added[pipe] / norm[pipe] for pipe in PIPES)
            mean = sum(added.values()) / len(PIPES)
            imbalance = max(abs(value - mean) for value in added.values())
            return (nmax, sum(loads[core].values()), imbalance, core)
        core = min(range(n), key=core_key)
        assignment[j] = core
        for pipe in PIPES:
            loads[core][pipe] += costs[j][pipe]
    plan_order = sorted(range(len(groups)), key=lambda j: min(groups[j]))
    return _plan(groups, assignment, plan_order, n, merge=True)


def _kios_low_comm_groups(m, n):
    """n-1 low-byte depth cuts of the dominant component, near equal node shares."""
    if not _dominant(m, n):
        return None
    big = max(range(len(m.components)), key=lambda j: sum(float(m.ops[u]['cycles']) for u in m.components[j]))
    members = set(m.components[big])
    depths = sorted({m.depth[u] for u in members})
    if len(depths) < n:
        return None
    prefix = {}
    count = 0
    for depth in depths:
        count += sum(1 for u in members if m.depth[u] == depth)
        prefix[depth] = count
    cut_cost = {}
    for depth in depths[:-1]:
        low = {u for u in members if m.depth[u] <= depth}
        high = members - low
        cut_cost[depth] = sum(
            size for (u, v), size in m.edge_bytes.items()
            if (u in low and v in high) or (u in high and v in low)
        )
    chosen = []
    window = max(1, int(0.10 * len(members)))
    for i in range(1, n):
        target = round(len(members) * i / n)
        pool = [depth for depth in depths[:-1] if abs(prefix[depth] - target) <= window and depth not in chosen]
        if not pool:
            pool = [depth for depth in depths[:-1] if depth not in chosen]
        if not pool:
            break
        chosen.append(min(pool, key=lambda depth: (cut_cost[depth], abs(prefix[depth] - target), depth)))
    chosen = sorted(set(chosen))
    if len(chosen) != n - 1:
        return None
    labels = {}
    next_label = len(chosen) + 1
    for j, comp in enumerate(m.components):
        if j == big:
            continue
        for u in comp:
            labels[u] = next_label
        next_label += 1
    for u in members:
        labels[u] = sum(1 for depth in chosen if m.depth[u] > depth)
    merged = {}
    for group in m.connected_groups(labels):
        label = labels[group[0]]
        merged[label] = sorted(merged[label] + group) if label in merged else list(group)
    groups = [merged[label] for label in sorted(merged)]
    if not _usable(m, groups):
        return None
    return groups


def _width_groups(m, width):
    if width <= 0:
        return None
    labels = {u: m.depth[u] // width for u in m.ids}
    groups = [group for group in m.connected_groups(labels) if group]
    if not _usable(m, groups):
        return None
    return groups


def _extra_component_bundles(m, n, add):
    """Whole-component bundles at sizes stitch does not already emit.

    Stitch emits size 3 on small graphs and sizes 4 and 8 up to 12000 nodes.
    Sizes 2 and 7 stay here. Sizes 9 and 10 did not win a problem-1 case.
    """
    from solver import _plan
    if len(m.ids) > 12000:
        return
    comps = sorted((sorted(group) for group in m.components), key=lambda group: group[0])
    if not 2 <= len(comps) <= 200:
        return
    for gsize in (2, 7):
        if gsize > len(comps):
            continue
        groups = []
        for start in range(0, len(comps), gsize):
            members = []
            for comp in comps[start:start + gsize]:
                members.extend(comp)
            groups.append(sorted(members))
        if not _usable(m, groups):
            continue
        duration = [sum(int(m.ops[node]['cycles']) for node in group) for group in groups]
        order = sorted(range(len(groups)), key=lambda index: (-duration[index], groups[index][0]))
        loads = [0] * n
        assignment = {}
        for index in order:
            core = min(range(n), key=lambda slot: (loads[slot], slot))
            assignment[index] = core
            loads[core] += duration[index]
        emit = sorted(range(len(groups)), key=lambda index: groups[index][0])
        try:
            add('component_group%d' % gsize, _plan(groups, assignment, emit, n, False))
        except ValueError:
            pass


def _legacy_scene_a(m, n, add):
    """9.24 Kios Scene A extras and the 9.24 NiuDs adaptive window.

    Skipped on large graphs so the extra official evaluations stay off the
    cases that already exceed the 600-second target.
    """
    import math
    from solver import _component_batch_plan, _heft_plan

    def heft_scene_a(model, groups, cores):
        return _heft_plan(model, groups, cores, 1, 1.0)

    if len(m.ids) > 12000:
        return
    try:
        add('kios_pipe_vector_lpt', _kios_pipe_vector(m, n))
    except ValueError:
        pass
    if 2 <= len(m.components) <= MAX_GROUPS:
        for target in (8, 4, 2):
            batch = max(32, min(2048, math.ceil(len(m.ids) / max(1, n * target))))
            try:
                add('kios_adaptive_batch_t%d' % target, _component_batch_plan(m, n, batch))
            except ValueError:
                pass
    if not _dominant(m, n):
        return
    depth = max(m.depth.values(), default=0)
    if depth:
        kios_width = max(4, min(64, math.ceil((depth + 1) / max(2, 4 * n))))
        groups = _width_groups(m, kios_width)
        if groups is not None:
            add('kios_window_adaptive_heft', _try_plan(heft_scene_a, m, groups, n))
            add('kios_window_adaptive_heft2', _try_plan(_heft2, m, groups, n))
        target_tasks = max(n * 8, math.ceil(len(m.ids) / max(1, n * 8)))
        niu_width = max(2, min(64, math.ceil(depth / target_tasks)))
        if niu_width != kios_width:
            groups = _width_groups(m, niu_width)
            if groups is not None:
                add('niu_window_adaptive_heft', _try_plan(heft_scene_a, m, groups, n))
                add('niu_window_adaptive_heft2', _try_plan(_heft2, m, groups, n))
    groups = _kios_low_comm_groups(m, n)
    if groups is not None:
        add('kios_low_comm_heft', _try_plan(heft_scene_a, m, groups, n))
        add('kios_low_comm_heft2', _try_plan(_heft2, m, groups, n))


def extra_plans(m, n):
    """Return ``(name, plan)`` pairs. Empty when the graph shape does not fit."""
    if n != 5 or not m.ids:
        return []
    out, seen = [], set()

    def add(name, plan):
        if plan is None:
            return
        if len(plan['node_to_subgraph']) != len(m.ids):
            return
        if len(plan['core_schedules']) != n:
            return
        fingerprint = (
            tuple(sorted(plan['node_to_subgraph'].items())),
            tuple(map(tuple, plan['core_schedules'])),
        )
        if fingerprint in seen:
            return
        seen.add(fingerprint)
        out.append((name, plan))

    _legacy_scene_a(m, n, add)
    _extra_component_bundles(m, n, add)

    # Only pipe_seg_1.0 won a problem-1 case. Other scales and the PEFT
    # insertion variants never did. Graphs above 20000 nodes skip it: those
    # merged tasks repeat an evaluation the kept plans already cover.
    if len(m.ids) <= 20000:
        groups = _pipeline_groups(m, n, 1.0)
        if groups is not None:
            add('pipe_seg_1.0', _plan_rr(groups, n))

    nodes = len(m.ids)
    # Multi-component graphs above 12000 nodes already keep a better winner.
    # A single component is the whole graph, so the same windows still apply
    # up to 16000 nodes. Larger single-component graphs stay on the kept set.
    single_component = len(m.components) == 1 and nodes <= 16000
    if _dominant(m, n) and (nodes <= 12000 or single_component):
        for narrow_w, wide_w, thresh in VW_CONFIGS:
            groups = _groups_from_depth_labels(
                m, _window_labels(m, narrow_w, wide_w, thresh))
            if not _usable(m, groups):
                continue
            add(
                'vw%d_%d_t%d_heft2' % (narrow_w, wide_w, thresh),
                _try_plan(_heft2, m, groups, n),
            )
            # Same windows, PEFT insertion. It improved the wider partitions
            # and lost on the short ones, so only the middle band is kept.
            if 60 <= len(groups) <= 320:
                add(
                    'vw%d_%d_t%d_peftins' % (narrow_w, wide_w, thresh),
                    _try_plan(_peft_insert, m, groups, n),
                )
        for narrow_w, wide_w, thresh, byte_cap in CAV_CONFIGS:
            groups = _groups_from_depth_labels(
                m, _window_labels(m, narrow_w, wide_w, thresh, byte_cap))
            if not _usable(m, groups):
                continue
            add(
                'cav%d_%d_t%d_b%d_peftins' % (narrow_w, wide_w, thresh, byte_cap),
                _try_plan(_peft_insert, m, groups, n),
            )
    return out
