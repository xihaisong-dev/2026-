"""Bounded heuristic repair: at most two affected tasks times two target cores."""
import copy
from collections import defaultdict
from q1_partition import repair
from q1_search_tools import replay
from q1_solver import validate


def guided_repair(g, old_plan, mapping, cores):
    baseline, _ = g.schedule(mapping, cores)
    duration, _, (groups, _, _, order) = g.costs(mapping)
    best, score = baseline, replay(g, baseline, duration)
    info = {'proposed': 1, 'valid': 1, 'selected_local': False,
            'global_proxy': score, 'selected_proxy': score}
    try:
        inherited = repair(g, old_plan, mapping)
    except (ValueError, RuntimeError):
        g.guided_repair_stats.append(info)
        return best
    old_groups = defaultdict(set)
    for u, s in old_plan['node_to_subgraph'].items():
        old_groups[s].add(int(u))
    affected = sorted((s for s in groups if groups[s] != old_groups[s]),
                      key=lambda s: (-duration[s], s))[:2]
    rank = {s: i for i, s in enumerate(order)}
    core_load = [sum(duration[s] for s in seq) for seq in inherited['core_schedules']]

    def consider(plan):
        nonlocal best, score
        info['proposed'] += 1
        try:
            validate(g, plan)
            value = replay(g, plan, duration)
        except (ValueError, RuntimeError):
            return
        info['valid'] += 1
        if value < score:
            best, score = plan, value
            info['selected_local'] = True

    consider(inherited)
    for s in affected:
        source = next(c for c, seq in enumerate(inherited['core_schedules']) if s in seq)
        targets = sorted((c for c in range(cores) if c != source),
                         key=lambda c: (core_load[c], c))[:2]
        for target in targets:
            trial = copy.deepcopy(inherited)
            trial['core_schedules'][source].remove(s)
            seq = trial['core_schedules'][target]
            position = next((i for i, t in enumerate(seq) if rank[t] > rank[s]), len(seq))
            seq.insert(position, s)
            consider(trial)
    info['selected_proxy'] = score
    g.guided_repair_stats.append(info)
    return best
