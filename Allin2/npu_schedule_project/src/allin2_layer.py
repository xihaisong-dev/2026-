"""Duration-calibrated assignments appended after the kept candidate list.

Two structural families, both scored later by the official evaluator:

* ``rebal*`` keeps an existing partition and only reassigns cores. The seeds
  are the depth-10 window and the component batches, which are the partitions
  whose core balance moved under a calibrated duration.
* ``heft_cal_*`` builds fresh depth windows on graphs from 12000 to 16000
  nodes. Variable-width windows already cover graphs up to 12000 nodes, and
  a single-component graph up to 16000. Graphs above 16000 nodes are left
  to the candidates already kept.
"""
from __future__ import annotations


def extra_layer(m, n, kept):
    if n != 5 or not m.ids:
        return []
    from calibrated_heft import build_plans, groups_of_plan, rebalanced_plans

    out = []
    seen = set()

    def add(name, plan):
        if plan is None:
            return
        if len(plan.get('node_to_subgraph', {})) != len(m.ids):
            return
        if len(plan.get('core_schedules', [])) != n:
            return
        fp = (
            tuple(sorted(plan['node_to_subgraph'].items())),
            tuple(map(tuple, plan['core_schedules'])),
        )
        if fp in seen:
            return
        seen.add(fp)
        out.append((name, plan))

    seeds = []
    for name, plan in kept:
        if name not in ('window10_heft', 'component_batches'):
            continue
        rec = groups_of_plan(plan)
        if rec is None:
            continue
        groups, _core = rec
        if 2 <= len(groups) <= 2000:
            seeds.append((name, plan))
    if seeds:
        for name, plan in rebalanced_plans(m, seeds, n, 1, blends=(0.0, 0.5)):
            add(name, plan)

    nodes = len(m.ids)
    if 12000 < nodes <= 16000:
        for name, plan in build_plans(m, n, 1):
            add(name, plan)
    return out
