"""HEFT-inspired gap insertion, adapted to task waits (not zero local DDR cost)."""
from q1_solver import topological


def earliest_gap(events, ready, duration, wait):
    """Events are (start, end, task); reserve waits on BOTH sides of a gap."""
    start = ready
    for index, (left, right, _) in enumerate(events):
        if start + duration + wait <= left:
            return start, index
        start = max(start, right + wait)
    return start, len(events)


def schedule(g, mapping, cores, insertion=True, communication_rank=False):
    duration, traffic, (_, pred, succ, order) = g.costs(mapping)
    # Rank is only a priority heuristic; actual readiness uses assigned cores.
    rank_wait = (g.same + (cores-1)*g.cross)/cores if communication_rank else g.same
    rank = {}
    for s in reversed(order):
        rank[s] = duration[s] + max((rank_wait + rank[v] for v in succ[s]), default=0)
    events = [[] for _ in range(cores)]
    end, assigned = {}, {}
    for s in topological(pred, succ, rank):
        options = []
        for c in range(cores):
            ready = max((end[p] + (g.cross if assigned[p] != c else 0) for p in pred[s]), default=0)
            if insertion:
                start, index = earliest_gap(events[c], ready, duration[s], g.same)
            else:
                start = max(ready, events[c][-1][1] + g.same if events[c] else 0)
                index = len(events[c])
            options.append((start + duration[s], c, start, index))
        finish, c, start, index = min(options)
        events[c].insert(index, (start, finish, s))
        end[s], assigned[s] = finish, c
    plan = {'node_to_subgraph': {str(u): mapping[u] for u in sorted(mapping)},
            'core_schedules': [[s for _, _, s in seq] for seq in events]}
    return plan, max(max(end.values(), default=0), traffic/g.bandwidth)
