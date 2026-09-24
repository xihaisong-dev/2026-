"""Critical HOL guided legal group insertion; fixed seed plus best branch search.

Observed idle intervals rank proposals, never certify counterfactual savings.
Only the official replay determines acceptance, including FIFO and bandwidth.
"""
import copy
from q2_evaluator import key
from q2_solver import SceneBGraph, owner_of
from q2_physical import legal_positions
from q2_guarded import structural
from q2_bottleneck_j import analyze
from q3_solver import evaluate, audit


def proposals(g, plan, result, settings, delay, budget):
    from multicore_cut_evaluate_problem_3 import _build_scene_b_tasks
    tasks, links, *_ = _build_scene_b_tasks(g.raw, plan, settings['bandwidth'], settings['capacity'])
    d = analyze(tasks, links, result, delay, settings['bandwidth'])
    owners = owner_of(plan)
    gaps = [h for h in d['hol'] if h['on_critical_graph']]
    out = []; seen = {key(plan)}
    # Interleave gaps: one large gap must not consume the whole evaluation budget.
    menus = []
    for h in gaps:
        actions = []
        for b in sorted(h['blocked'], key=lambda b: (-b['opportunity'], b['op'])):
            if b['group'] in owners and b['group'] != h['head_group']:
                actions.append((b['group'], owners[b['group']], 'bypass', h['head_group']))
        for s in h['releasing_groups']:
            if s in owners:
                actions.append((s, owners[s], 'producer_advance', None))
        menu = []
        for s, c, kind, head in actions:
            seqs, lo, hi = legal_positions(g, plan, s, c)
            old = plan['core_schedules'][c].index(s)
            # Same-core moves first isolate timing/order from added cross-core copies.
            if kind == 'bypass':
                if head not in seqs[c]: continue
                target = seqs[c].index(head)
                positions = [target, lo]
            else:
                positions = [lo, max(lo, old-1)]
            for at in dict.fromkeys(positions):
                if not lo <= at <= hi or at >= old: continue
                p = dict(node_to_subgraph=dict(plan['node_to_subgraph']), core_schedules=copy.deepcopy(seqs))
                p['core_schedules'][c].insert(at, s)
                structural(g, p)
                menu.append(dict(plan=p, move=dict(kind=kind, group=s, core=c, position=at,
                    head_group=h['head_group'], head_op=h['head_op'], pipe=h['pipe'],
                    observed_gap=[h['idle_start'], h['idle_end']], opportunity_cycles=h['opportunity_cycles'])))
        menus.append(iter(menu))
    while menus and len(out) < budget:
        remaining = []
        for menu in menus:
            for x in menu:
                digest = key(x['plan'])
                if digest in seen: continue
                seen.add(digest); out.append(x); remaining.append(menu); break
            if len(out) >= budget: break
        menus = remaining
    return out, dict(critical_hol_count=len(gaps), total_hol_count=len(d['hol']),
        start_reconstruction_error=d['start_reconstruction_max_error'], proposals=len(out))


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
