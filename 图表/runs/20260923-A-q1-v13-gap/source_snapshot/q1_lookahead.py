"""Bounded critical-region split search, ordered by predicted makespan."""
from collections import defaultdict


def candidates(g, plan, result, cores):
    from q1_experimental import task_slacks
    mapping = {int(u): s for u, s in plan['node_to_subgraph'].items()}
    groups, _, _, _ = g.view(mapping)
    slack = task_slacks(g, plan, result)
    tasks = [t for c in result['per_core_timeline'] for t in c['tasks']]
    tasks.sort(key=lambda t: (slack[t['task_id']], -t['duration'], t['task_id']))
    pool = []
    # Limit construction work: four bottlenecks, at most three cut locations each.
    for task in tasks[:4]:
        s = task['task_id']
        nodes = sorted(groups[s], key=g.pos.get)
        if len(nodes) < 2:
            continue
        loads = defaultdict(int)
        for u in nodes:
            loads[g.ops[u]['pipe']] += g.ops[u]['cycles']
        pipe = max(loads, key=lambda p: (loads[p], p))
        weights = [g.ops[u]['cycles'] if g.ops[u]['pipe'] == pipe else 0 for u in nodes]
        prefix, positions = 0, []
        for i, w in enumerate(weights[:-1], 1):
            prefix += w
            positions.append((prefix, i))
        cuts = sorted({min(positions, key=lambda x: (abs(x[0]-loads[pipe]*fraction), x[1]))[1]
                       for fraction in (.25, .5, .75)})
        for cut in cuts:
            trial = dict(mapping)
            for u in nodes[cut:]:
                trial[u] = max(groups)+1
            try:
                proposed, proxy = g.schedule(trial, cores)
            except ValueError:
                continue
            pool.append((proxy, s, cut, proposed))
    # This is an ordering proxy, not a bound or acceptance criterion.
    for _, s, cut, proposed in sorted(pool, key=lambda x: x[:3]):
        yield f'lookahead_split_{s}_{cut}', proposed
