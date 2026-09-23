"""Bounded multi-placement search; official evaluation remains unchanged."""
from q1_insertion import earliest_gap, schedule as insertion_schedule
from q1_search_tools import replay
from q1_solver import topological


def schedule(g, mapping, cores, width=8, max_tasks=128):
    if width < 1 or cores < 1:
        raise ValueError('width and cores must be positive')
    baseline, _ = insertion_schedule(g, mapping, cores, True, True)
    duration, traffic, (_, pred, succ, order) = g.costs(mapping)
    baseline_score = replay(g, baseline, duration)
    info = {'tasks': len(order), 'expanded': 0, 'fallback': len(order) > max_tasks,
            'baseline_proxy': baseline_score, 'selected_proxy': baseline_score}
    if len(order) > max_tasks or cores == 1:
        return baseline, baseline_score, info
    rank, tail = {}, {}
    rank_wait = (g.same + (cores - 1) * g.cross) / cores
    for s in reversed(order):
        tail[s] = max((duration[v] + tail[v] for v in succ[s]), default=0)
        rank[s] = duration[s] + max((rank_wait + rank[v] for v in succ[s]), default=0)
    sequence = topological(pred, succ, rank)
    # Events, finish times and owners of the already placed tasks.
    beam = [([[] for _ in range(cores)], {}, {})]
    work_floor = sum(duration.values()) / cores
    for s in sequence:
        pool = []
        for events, end, owner in beam:
            empty_seen = False
            for c in range(cores):
                # Empty homogeneous cores are interchangeable at this point.
                if not events[c]:
                    if empty_seen:
                        continue
                    empty_seen = True
                ready = max((end[p] + (g.cross if owner[p] != c else 0)
                             for p in pred[s]), default=0)
                start, index = earliest_gap(events[c], ready, duration[s], g.same)
                finish = start + duration[s]
                next_events = [list(x) for x in events]
                next_events[c].insert(index, (start, finish, s))
                next_end, next_owner = dict(end), dict(owner)
                next_end[s], next_owner[s] = finish, c
                # Optimistic proxy for this frozen-duration model, NOT an official bound.
                estimate = max(work_floor, traffic / g.bandwidth,
                               max(next_end[u] + tail[u] for u in next_end))
                signature = tuple(tuple(t for _, _, t in seq) for seq in next_events)
                pool.append((estimate, max(next_end.values()), signature,
                             next_events, next_end, next_owner))
                info['expanded'] += 1
        pool.sort(key=lambda x: x[:3])
        beam = [(x[3], x[4], x[5]) for x in pool[:width]]
    selected, score = baseline, baseline_score
    for events, _, _ in beam:
        plan = {'node_to_subgraph': dict(baseline['node_to_subgraph']),
                'core_schedules': [[s for _, _, s in seq] for seq in events]}
        value = replay(g, plan, duration)
        if value < score:
            selected, score = plan, value
    info['selected_proxy'] = score
    return selected, score, info
