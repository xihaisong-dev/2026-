"""Same r04 search decisions with lazily generated, order-identical proposals."""
from q2_evaluator import key
from q2_solver import SceneBGraph
from q3_solver import evaluate,audit
from q3_asap_fast import proposals

def solve(raw, seed, s, d, c, mode, budget=24):
    anchor = evaluate(raw, seed, s, d, c); g = SceneBGraph(raw, s, d)
    objective = lambda r: (r['makespan'], r['data_movement_bytes']['added_copy_bytes'])
    best, result = seed, anchor
    seen = {key(seed)}; evaluations = []; rounds = []; menus = {}
    def menu(plan, r):
        h = key(plan)
        if h not in menus:
            xs, diagnostic = proposals(g, plan, r, s, d, budget)
            menus[h] = iter(xs)
            rounds.append(dict(seed=h, before=r['makespan'], diagnostic=diagnostic))
        return menus[h]
    root = menu(seed, anchor)
    while len(evaluations) < budget:
        changed = False; tried = False
        # Keep root alive. Each sweep allocates up to four calls to each branch.
        branches = [(seed, anchor)]
        if mode == 'beam' and key(best) != key(seed): branches.append((best, result))
        for base, r0 in branches:
            queue = root if key(base) == key(seed) else menu(base, r0)
            calls = 0
            for x in queue:
                h = key(x['plan'])
                if h in seen: continue
                seen.add(h); tried = True; calls += 1
                r = evaluate(raw, x['plan'], s, d, c)
                improved = objective(r) < objective(result)
                evaluations.append(dict(plan_sha256=h, parent=key(base), move=x['move'],
                    makespan=r['makespan'], added_bytes=objective(r)[1], accepted=improved))
                if improved: best, result = x['plan'], r; changed = True
                if calls == 4 or len(evaluations) == budget: break
            if len(evaluations) == budget: break
        if not tried and not changed: break
    replay = evaluate(raw, best, s, d, c)
    assert replay == result and objective(result) <= objective(anchor)
    return best, result, anchor, dict(mode=mode, budget=budget, evaluations=evaluations,
        rounds=rounds, replay_equal=True, checks=audit(raw, best, result, s, d))
