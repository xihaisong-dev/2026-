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


def routed_candidates(raw, settings, waits, cores, kind, ranking="local", ranker=None):
    """Only replace an old rejected route; keep eligible old seeds unchanged."""
    from q1_structural_seeds import guarded_component_candidate
    from q1_local_rank import LocalRank
    from q1_experimental import CostGraph
    plans, info = guarded_component_candidate(raw, settings, waits, cores,
                                               max_candidates=2, ranking=ranking, ranker=ranker)
    gate = info['gate']
    if kind == 'auto':
        kind = 'memory' if gate == 'all_components_have_large_union_footprint' else 'hybrid'
    allowed = (kind == 'memory' and gate == 'all_components_have_large_union_footprint') or (
        kind == 'hybrid' and gate == 'dominant_component')
    if not allowed:
        return plans, info
    m = GraphModel(raw, settings, waits)
    pool = memory_pool(m, cores) if kind == 'memory' else hybrid_pool(m, cores)
    ranker = ranker or LocalRank(raw, CostGraph(raw, settings, waits, False), event=ranking=='event')
    ranked = []
    global_before = ranker.preparer.evaluations
    for i, (name, plan) in enumerate(pool):
        prediction, _, _ = ranker.score(plan)
        loads = [dict.fromkeys(PIPES, 0.) for _ in range(cores)]
        core_of = {s:c for c,seq in enumerate(plan['core_schedules']) for s in seq}
        for u in m.ids:
            c = core_of[plan['node_to_subgraph'][str(u)]]
            loads[c][m.ops[u]['pipe']] += m.ops[u]['cycles']
        bound = max(max(v.values()) for v in loads)
        local = ranker.last_components.get('local', prediction)
        event = prediction if ranker.event else None
        ranked.append((event if ranking=='event' else local, i, name, plan, bound, local, event))
    assert ranker.preparer.evaluations == global_before
    info['ranking_global_evaluations'] = 0
    ranked.sort(key=lambda x:x[:2]); best = ranked[0]
    info.update(route=kind, ranking='event_profiles_frozen_state' if ranking=='event' else 'local_task_profiles_frozen_state',
                ranked=[dict(candidate=x[2],local_prediction=x[5],compute_lower_bound=x[4],**({'event_prediction':x[6]} if x[6] is not None else {})) for x in ranked],
                local_preparation=ranker.stats(), generated=[best[2]],
                selected_compute_lower_bound=best[4], candidate_compute_bounds={best[2]:best[4]})
    return [(best[2],best[3])], info
