"""Shared-input coarsening and placement-preserving structural repair."""
from collections import defaultdict
from itertools import combinations
from q1_solver import validate


def shared_pairs(g, mapping):
    groups = g.view(mapping)[0]
    affinity = defaultdict(int)
    for size, _, producers, consumers, _ in g.tensors:
        if producers:
            continue
        touched = sorted({mapping[u] for u in consumers},
                         key=lambda s: (min(g.pos[u] for u in groups[s]), s))
        # Avoid quadratic expansion for very wide input hyperedges.
        pairs = combinations(touched, 2) if len(touched) <= 16 else zip(touched, touched[1:])
        for a, b in pairs:
            affinity[tuple(sorted((a, b)))] += size
    return affinity


def shared_coarsen(g, initial, cores, limit=16):
    mapping = dict(initial)
    _, best = g.schedule(mapping, cores)
    groups, pred, succ, _ = g.view(mapping)
    loads = {s: defaultdict(int) for s in groups}
    for u, s in mapping.items():
        loads[s][g.ops[u]['pipe']] += g.ops[u]['cycles']
    proposals = []
    pairs = shared_pairs(g, mapping)
    info = {'shared_pairs': len(pairs), 'positive_pairs': 0, 'attempted': 0, 'accepted': 0}
    for (a, b), saved in pairs.items():
        pipes = set(loads[a]) | set(loads[b])
        combined = max((loads[a][p]+loads[b][p] for p in pipes), default=0)
        parallel_loss = max(0, combined-max(max(loads[a].values(), default=0),
                                             max(loads[b].values(), default=0)))
        # This is only screening: serial dependent pairs don't lose parallelism.
        if b in succ[a] or a in succ[b]:
            parallel_loss = 0
        benefit = saved/g.bandwidth-parallel_loss
        if benefit > 0:
            proposals.append((-benefit, a, b))
    used = set()
    info['positive_pairs'] = len(proposals)
    for _, a, b in sorted(proposals)[:limit]:
        if a in used or b in used or len(groups[a])+len(groups[b]) > 1024:
            continue
        trial = {u: a if s == b else s for u, s in mapping.items()}
        info['attempted'] += 1
        try:
            _, estimate = g.schedule(trial, cores)
        except ValueError:
            continue
        if estimate <= best:
            mapping, best = trial, estimate
            used.update((a, b))
            info['accepted'] += 1
    g.shared_input_stats = info
    return mapping


def repair(g, old_plan, mapping):
    """Keep unaffected tasks' core and relative order; reject infeasible repairs."""
    old = {int(u): s for u, s in old_plan['node_to_subgraph'].items()}
    groups, _, _, order = g.view(mapping)
    old_groups = defaultdict(set)
    for u, s in old.items():
        old_groups[s].add(u)
    anchors = defaultdict(list)
    rank = {s: i for i, s in enumerate(order)}
    for s, members in groups.items():
        if s in old_groups:
            anchor = s
        else:
            overlap = defaultdict(int)
            for u in members:
                overlap[old[u]] += 1
            anchor = min(overlap, key=lambda a: (-overlap[a], a))
        anchors[anchor].append(s)
    plan = {'node_to_subgraph': {str(u): mapping[u] for u in sorted(mapping)},
            'core_schedules': [[s for old_s in seq
                                for s in sorted(anchors[old_s], key=rank.get)]
                               for seq in old_plan['core_schedules']]}
    validate(g, plan)
    return plan
