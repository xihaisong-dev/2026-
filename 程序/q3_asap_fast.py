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
    intervals = {}
    def gap_menu(h):
        actions = []
        for b in sorted(h['blocked'], key=lambda b: (-b['opportunity'], b['op'])):
            if b['group'] in owners and b['group'] != h['head_group']:
                actions.append((b['group'], owners[b['group']], 'bypass', h['head_group']))
        for s in h['releasing_groups']:
            if s in owners:
                actions.append((s, owners[s], 'producer_advance', None))
        for s, c, kind, head in actions:
            if (s,c) not in intervals: intervals[s,c] = legal_positions(g, plan, s, c)
            seqs, lo, hi = intervals[s,c]
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
                yield dict(plan=p, move=dict(kind=kind, group=s, core=c, position=at,
                    head_group=h['head_group'], head_op=h['head_op'], pipe=h['pipe'],
                    observed_gap=[h['idle_start'], h['idle_end']], opportunity_cycles=h['opportunity_cycles']))
    menus = [gap_menu(h) for h in gaps]
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

