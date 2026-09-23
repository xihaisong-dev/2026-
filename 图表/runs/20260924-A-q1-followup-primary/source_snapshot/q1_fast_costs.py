"""Exact per-group memoization of the existing (approximate) Graph.costs model.

Boundary reads/writes and liveness depend only on the group's membership, not
the IDs or placement of other groups. Cache the uncalibrated base only; observed
local durations are applied afresh by CostGraph. Limit the cache to 8192 groups.
"""
from collections import OrderedDict, defaultdict
import math


def costs(g, mapping):
    view = g.view(mapping)
    groups = view[0]
    if not hasattr(g, '_base_group_cache'):
        g._base_group_cache = OrderedDict()
    cache = g._base_group_cache
    ordered = {s: [] for s in groups}
    for u, s in mapping.items():
        ordered[s].append(u)
    duration, traffic = {}, 0
    for s, nodes in groups.items():
        # Preserve original floating-point addition order for arbitrary inputs.
        key = tuple(ordered[s])
        if key in cache:
            value, local_traffic = cache[key]
            cache.move_to_end(key)
        else:
            loads = defaultdict(float)
            for u in ordered[s]:
                loads[g.ops[u]['pipe']] += g.ops[u]['cycles']
            events = defaultdict(lambda: defaultdict(int))
            local_traffic = 0
            touched = sorted({i for u in nodes for i in g.incident[u]})
            for i in touched:
                size, pos, ps, cs, final = g.tensors[i]
                local_p, local_c = ps & nodes, cs & nodes
                if bool(local_c) and not local_p:
                    loads['PIPE_MTE2'] += math.ceil(size / g.bandwidth)
                    local_traffic += size
                if bool(local_p) and (final or not cs or bool(cs - nodes)):
                    loads['PIPE_MTE3'] += math.ceil(size / g.bandwidth)
                    local_traffic += size
                uses = [g.pos[u] for u in local_p | local_c]
                events[min(uses)][pos] += size
                events[max(uses) + 1][pos] -= size
            live, peak = defaultdict(int), defaultdict(int)
            for i in sorted(events):
                for pos, delta in events[i].items():
                    live[pos] += delta
                    peak[pos] = max(peak[pos], live[pos])
            pressure = sum(max(0, peak[p] - cap) for p, cap in g.capacity.items())
            value = max(loads.values(), default=0) + 2 * pressure / g.bandwidth
            cache[key] = value, local_traffic
            if len(cache) > 8192:
                cache.popitem(last=False)
        duration[s] = value
        traffic += local_traffic
    return duration, traffic, view
