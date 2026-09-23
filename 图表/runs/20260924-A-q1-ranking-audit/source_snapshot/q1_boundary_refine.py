"""At most three greedy boundary steps and four legal-move probes per step."""
from q1_frozen_cost import FrozenCost
from q1_region import candidates, rebuild
from q1_search_tools import canonical


def pool(g, plan, result, cores, calibrate=False, refine=False):
    frozen = FrozenCost(g, plan, result)
    proposals = list(candidates(frozen.g, plan, result, cores, all_candidates=True))
    region = set(frozen.g.region_stats[-1]['region'])
    info = {'frozen_state': frozen.state, 'calibration': frozen.calibration,
            'base_candidates': len(proposals), 'boundary_probes': 0,
            'boundary_valid': 0, 'accepted_steps': 0, 'accepted_scores': [],
            'calibrate': calibrate, 'refine': refine}
    scored = [(frozen.score(p, calibrate), name, p) for name, p in proposals]
    # Refinement starts from the incumbent; it cannot touch exterior members.
    current = {int(u): s for u, s in plan['node_to_subgraph'].items()}
    value = frozen.score(plan, calibrate)
    locked = set()
    if refine and region:
        for step in range(3):
            groups = frozen.g.view(current)[0]
            moves = set()
            for u in sorted(current):
                if current[u] not in region:
                    continue
                for v in sorted(g.succ[u]):
                    if current[v] in region and current[u] != current[v]:
                        moves.update([(u, current[v]), (v, current[u])])
            def affinity(move):
                u, target = move
                shared = sum(g.tensors[t][0] for t in g.incident[u]
                             if (g.tensors[t][2] | g.tensors[t][3]) & groups[target])
                return -shared, u, target
            options = []
            for u, target in sorted((m for m in moves if m[0] not in locked), key=affinity)[:4]:
                info['boundary_probes'] += 1
                trial = dict(current)
                trial[u] = target
                try:
                    # view/rebuild rejects quotient or exterior-order cycles.
                    candidate, _ = rebuild(frozen.g, plan, trial, region, cores)
                    score = frozen.score(candidate, calibrate)
                except (ValueError, RuntimeError):
                    continue
                info['boundary_valid'] += 1
                options.append((score, u, target, candidate, trial))
            if not options:
                break
            score, u, target, candidate, trial = min(options, key=lambda x: x[:3])
            if score >= value-1e-8:
                break
            current, value = trial, score
            locked.add(u)
            info['accepted_steps'] += 1
            info['accepted_scores'].append(score)
            scored.append((score, f'fm_{step+1}_{u}_{target}', candidate))
    unique, seen = [], {canonical(plan)}
    for score, label, candidate in sorted(scored, key=lambda x: (x[0], x[1])):
        key = canonical(candidate)
        if key not in seen:
            seen.add(key)
            unique.append((score, label, candidate))
    frozen.check()
    g.region_stats.extend(frozen.g.region_stats)
    g.boundary_stats.append(info)
    return unique, frozen


def ranked_candidates(g, plan, result, cores, calibrate=False, refine=False):
    ranked, _ = pool(g, plan, result, cores, calibrate, refine)
    for _, label, candidate in ranked[:2]:
        yield label, candidate
