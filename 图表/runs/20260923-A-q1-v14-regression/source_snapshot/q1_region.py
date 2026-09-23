"""Bounded critical-region destroy and greedy repair (no joint enumeration)."""
from q1_insertion import earliest_gap
from q1_solver import topological, validate
from q1_search_tools import replay, canonical


def rebuild(g, old, mapping, region, cores, mode=0, gap=False):
    duration, _, (groups, pred, succ, order) = g.costs(mapping)
    exterior = {s for s in old['node_to_subgraph'].values() if s not in region}
    owner = {s: c for c, seq in enumerate(old['core_schedules']) for s in seq if s in exterior}
    # Fixed exterior order is a hard DAG constraint, not a timing penalty.
    for seq in old['core_schedules']:
        fixed = [s for s in seq if s in exterior]
        for a, b in zip(fixed, fixed[1:]):
            pred[b].add(a)
            succ[a].add(b)
    order = topological(pred, succ)
    tail = {}
    for s in reversed(order):
        tail[s] = duration[s] + max((tail[v] for v in succ[s]), default=0)
    priority = tail if mode == 0 else {s: duration[s] for s in groups}
    end, assigned = {}, {}
    seqs = [[] for _ in range(cores)]
    events = [[] for _ in range(cores)]
    for s in topological(pred, succ, priority):
        choices = []
        for c in ([owner[s]] if s in exterior else range(cores)):
            ready = max((end[a] + (g.cross if assigned[a] != c else 0)
                         for a in pred[s]), default=0)
            if gap:
                start, index = earliest_gap(events[c], ready, duration[s], g.same)
            else:
                start = max(ready, events[c][-1][1] + g.same if events[c] else 0)
                index = len(events[c])
            choices.append((start + duration[s], c, start, index))
        end[s], c, start, index = min(choices)
        assigned[s] = c
        events[c].insert(index, (start, end[s], s))
        seqs[c].insert(index, s)
    plan = {'node_to_subgraph': {str(u): mapping[u] for u in sorted(mapping)},
            'core_schedules': seqs}
    validate(g, plan)
    return plan, replay(g, plan, duration)


def candidates(g, plan, result, cores, gap=False, all_candidates=False):
    from q1_experimental import task_slacks
    mapping = {int(u): s for u, s in plan['node_to_subgraph'].items()}
    groups, pred, succ, _ = g.view(mapping)
    tasks = {t['task_id']: t for c in result['per_core_timeline'] for t in c['tasks']}
    slack = task_slacks(g, plan, result)
    key = lambda s: (slack[s], -tasks[s]['duration'], s)
    adjacency = {s: pred[s] | succ[s] for s in groups}
    for seq in plan['core_schedules']:
        for a, b in zip(seq, seq[1:]):
            adjacency[a].add(b)
            adjacency[b].add(a)
    # One seed, <=4 tasks and <=512 operations. Large tasks are not silently split.
    eligible = [s for s in groups if len(groups[s]) <= 512]
    info = {'region': [], 'nodes': 0, 'mapping_proposals': 0, 'plan_proposals': 0,
            'valid': 0, 'returned': 0, 'gap': gap}
    g.region_stats.append(info)
    if not eligible:
        return
    region = {min(eligible, key=key)}
    nodes = set(groups[next(iter(region))])
    while len(region) < 4:
        frontier = set().union(*(adjacency[s] for s in region)) - region
        frontier = [s for s in frontier if len(nodes) + len(groups[s]) <= 512]
        if not frontier:
            break
        s = min(frontier, key=key)
        region.add(s)
        nodes.update(groups[s])
    info.update(region=sorted(region), nodes=len(nodes))
    variants = [('placement', mapping)]
    ordered = sorted(nodes, key=g.pos.get)
    # Three bounded coarsening/refinement alternatives, balanced by compute work.
    for count in sorted({max(1, len(region)-1), len(region), min(4, len(region)+1)}):
        if count > len(nodes):
            continue
        ids = sorted(region) + list(range(max(groups)+1, max(groups)+1+count))
        trial, cumulative, bucket = dict(mapping), 0, 0
        total = sum(max(1, g.ops[u]['cycles']) for u in ordered)
        for i, u in enumerate(ordered):
            if bucket < count-1 and i >= bucket+1 and cumulative >= total*(bucket+1)/count:
                bucket += 1
            trial[u] = ids[bucket]
            cumulative += max(1, g.ops[u]['cycles'])
        variants.append(('repartition_'+str(count), trial))
    # Move one high-affinity boundary operation in either direction, only inside region.
    edges = [(u, v) for u in ordered for v in sorted(g.succ[u])
             if v in nodes and mapping[u] != mapping[v]]
    if edges:
        u, v = max(edges, key=lambda e: (sum(g.tensors[t][0] for t in
                        set(g.incident[e[0]]) & set(g.incident[e[1]])), -e[0], -e[1]))
        for a, b in [(u, v), (v, u)]:
            trial = dict(mapping)
            trial[a] = mapping[b]
            variants.append(('boundary_'+str(a), trial))
    pool, seen_maps, seen_plans = [], set(), {canonical(plan)}
    for label, trial in variants[:6]:
        mk = tuple(sorted(trial.items()))
        if mk in seen_maps:
            continue
        seen_maps.add(mk)
        info['mapping_proposals'] += 1
        for mode in range(2):
            info['plan_proposals'] += 1
            try:
                candidate, score = rebuild(g, plan, trial, region, cores, mode, gap)
            except (ValueError, RuntimeError):
                continue
            info['valid'] += 1
            ck = canonical(candidate)
            if ck in seen_plans:
                continue
            seen_plans.add(ck)
            pool.append((score, label+'_'+str(mode), candidate))
    # Two distinct candidates, not all partitions, assignments or permutations.
    for score, label, candidate in sorted(pool, key=lambda x: (x[0], x[1]))[:12 if all_candidates else 2]:
        info['returned'] += 1
        yield label, candidate
