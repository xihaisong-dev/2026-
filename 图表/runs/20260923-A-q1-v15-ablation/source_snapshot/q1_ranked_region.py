"""Exact local reranking, optional bounded expansion or best-prefix repair."""
from q1_frozen_cost import FrozenCost
from q1_local_rank import LocalRank
from q1_region import candidates, rebuild
from q1_search_tools import canonical


def structure(plan):
    # Ignore arbitrary Task IDs for diversity; retain core and sequence semantics.
    groups = {}
    for u,s in plan['node_to_subgraph'].items():
        groups.setdefault(s, []).append(int(u))
    return tuple(tuple(tuple(sorted(groups[s])) for s in seq) for seq in plan['core_schedules'])


def ranked_candidates(g, raw, plan, result, cores, wide=False, uphill=False):
    frozen = FrozenCost(g, plan, result)
    ranker = LocalRank(raw, frozen.g)
    info = {'kind': 'local_exact', 'wide': wide, 'uphill': uphill,
            'regions': [], 'probes': 0, 'valid_moves': 0, 'walk_scores': [],
            'unique_candidates': 0, 'state_sha256': frozen.state}
    diversity_key = structure if wide or uphill else canonical
    seen = {diversity_key(plan)}
    scored = []
    incumbent_score = ranker.score(plan)[0]

    def add(label, candidate):
        key = diversity_key(candidate)
        if key in seen:
            return None
        seen.add(key)
        value = ranker.score(candidate)[0]
        scored.append((value, label, candidate))
        return value

    for size in ([4,8,12] if wide else [4]):
        batch = list(candidates(frozen.g, plan, result, cores, all_candidates=True, max_tasks=size))
        region = set(frozen.g.region_stats[-1]['region'])
        info['regions'].append(sorted(region))
        for label, candidate in batch:
            add(f'r{size}_{label}', candidate)
        # Expansion only when diversity is insufficient or no predicted gain.
        if len(scored) >= 6 and min(x[0] for x in scored) < incumbent_score:
            break
    if uphill and region:
        current = {int(u): s for u,s in plan['node_to_subgraph'].items()}
        best_value, best_plan = incumbent_score, None
        locked = set()
        for step in range(6):
            groups = frozen.g.view(current)[0]
            moves = set()
            for u in sorted(current):
                if current[u] not in region or u in locked:
                    continue
                for v in sorted(g.succ[u] | g.pred[u]):
                    if current[v] in region and current[v] != current[u]:
                        moves.add((u,current[v]))
            def affinity(move):
                u,target = move
                return (-sum(g.tensors[t][0] for t in g.incident[u]
                         if (g.tensors[t][2] | g.tensors[t][3]) & groups[target]),u,target)
            options = []
            for u,target in sorted(moves, key=affinity)[:4]:
                info['probes'] += 1
                trial = dict(current); trial[u] = target
                try:
                    candidate,_ = rebuild(frozen.g, plan, trial, region, cores)
                except (ValueError,RuntimeError):
                    continue
                value = ranker.score(candidate)[0]
                info['valid_moves'] += 1
                options.append((value,u,target,trial,candidate))
            if not options:
                break
            value,u,target,current,candidate = min(options,key=lambda x:x[:3])
            # Bounded deterioration: at most 2% over the starting proxy cost.
            if value > incumbent_score*1.02:
                break
            locked.add(u)
            info['walk_scores'].append(value)
            if value < best_value:
                best_value,best_plan = value,candidate
        if best_plan is not None:
            add('best_prefix',best_plan)
    frozen.check()
    info.update(unique_candidates=len(scored), preparation=ranker.stats())
    g.region_stats.extend(frozen.g.region_stats)
    g.boundary_stats.append(info)
    for _,label,candidate in sorted(scored,key=lambda x:(x[0],x[1]))[:2]:
        yield label,candidate
