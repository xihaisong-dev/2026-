"""Bounded structural alternatives for previously rejected component routes."""
from collections import defaultdict
from q1_structural_seeds import GraphModel, _component_plan, _plan, _heft_plan, PIPES, canonical_key


def memory_pool(m, cores):
    """Probe whole layouts and work-sized batches; no fixed operator count."""
    pool = [('memory_lpt', _component_plan(m, cores, 'lpt', True)),
            ('memory_pipe', _component_plan(m, cores, 'pipe', True))]
    layout = pool[-1][1]['node_to_subgraph']
    target = sum(max(m.cost_vector(c).values()) for c in m.components) / (2 * cores)
    groups, assignment, order = [], {}, []
    def emit(batch, core):
        if batch:
            sid = len(groups); groups.append(batch); assignment[sid] = core; order.append(sid)
    for core in range(cores):
        batch, work = [], 0.
        for component in sorted(m.components, key=min):
            if layout[str(component[0])] != core:
                continue
            cost = max(m.cost_vector(component).values())
            if batch and work + cost > target:
                emit(batch, core); batch, work = [], 0.
            batch = batch + component; work += cost
        emit(batch, core)
    pool.append(('memory_batches', _plan(groups, assignment, order, cores)))
    return unique(pool)


def hybrid_pool(m, cores):
    """Cut only heavy components into consecutive topological work windows."""
    weights = [max(m.cost_vector(c).values()) for c in m.components]
    average = sum(weights) / cores
    topo_index = {u: i for i, u in enumerate(m.topo)}
    pool = []
    for fraction in (1., .5):
        groups = []
        for component, weight in zip(m.components, weights):
            if weight <= average:
                groups.append(component)
                continue
            chunk, load = [], dict.fromkeys(PIPES, 0.)
            pieces = 0
            target = max(1., average * fraction)
            # At most 2*cores cuts per heavy component; never enumerate boundaries.
            for u in sorted(component, key=topo_index.__getitem__):
                pipe, cycles = m.ops[u]['pipe'], m.ops[u]['cycles']
                if chunk and pieces < 2 * cores - 1 and max(max(load.values()), load[pipe] + cycles) > target:
                    groups.append(chunk); pieces += 1; chunk, load = [], dict.fromkeys(PIPES, 0.)
                chunk.append(u); load[pipe] += cycles
            if chunk: groups.append(chunk)
        pool.append((f'hybrid_work_{fraction:g}', _heft_plan(m, groups, cores, 1)))
    return unique(pool)


def unique(pool):
    result, seen = [], set()
    for name, plan in pool:
        key = canonical_key(plan)
        if key not in seen:
            seen.add(key); result.append((name, plan))
    return result
