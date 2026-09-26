"""Official-evaluator local search on one already selected plan.

The partition ``node_to_subgraph`` stays fixed. Only subgraph-to-core moves
and swaps are tried, and each core order is rebuilt by a fixed topological
rank. The seed plan is kept unless a neighbor is strictly better on
``(makespan, added_copy_bytes)``. Graphs above 9000 compute nodes are skipped:
those official evaluations are slow and have not repaid the search.
"""
from __future__ import annotations

import heapq
import time
from collections import defaultdict

from evaluate import evaluate_plan


def budgets_for(nops):
    """Return ``(max_iter, top_t, eval_budget)`` or None when search is skipped."""
    if nops > 9000:
        return None
    if nops <= 1500:
        return 14, 16, 1200
    if nops <= 4000:
        return 6, 8, 300
    return 3, 5, 100


def local_search(graph, m, seed_plan, config, n, max_iter, top_t, max_evals, deadline=None):
    """Return ``(makespan, added_copy_bytes, plan)`` or None if the seed is invalid.

    ``deadline`` is a ``time.perf_counter`` timestamp. The seed evaluation
    always finishes. After that, an expired deadline returns the best neighbor
    already scored and does not start another official evaluation.
    """
    mp = {int(k): v for k, v in seed_plan['node_to_subgraph'].items()}
    subs = sorted(set(mp.values()))
    succ = defaultdict(set)
    indeg = defaultdict(int)
    seen_edge = set()
    for u in m.ids:
        a = mp[u]
        for v in m.succ[u]:
            b = mp[v]
            if a != b and (a, b) not in seen_edge:
                seen_edge.add((a, b))
                succ[a].add(b)
                indeg[b] += 1
    for s in subs:
        indeg.setdefault(s, 0)
    q = [s for s in subs if indeg[s] == 0]
    heapq.heapify(q)
    rank = {}
    i = 0
    while q:
        s = heapq.heappop(q)
        rank[s] = i
        i += 1
        for t in sorted(succ[s]):
            indeg[t] -= 1
            if indeg[t] == 0:
                heapq.heappush(q, t)
    if len(rank) != len(subs):
        return None
    pipe_by_sub = defaultdict(lambda: defaultdict(float))
    for u in m.ids:
        op = m.ops[u]
        pipe_by_sub[mp[u]][op['pipe']] += float(op['cycles'])
    bottleneck = {s: (max(pipe_by_sub[s].values()) if pipe_by_sub[s] else 0.0) for s in subs}

    def build(assign):
        sched = [[] for _ in range(n)]
        for s, c in assign.items():
            sched[c].append(s)
        for c in range(n):
            sched[c].sort(key=lambda s: rank[s])
        return {'node_to_subgraph': {str(u): mp[u] for u in m.ids}, 'core_schedules': sched}

    cache = {}
    evals = [0]

    def ev(assign):
        key = tuple(sorted(assign.items()))
        if key in cache:
            return cache[key]
        if evals[0] >= max_evals:
            return (float('inf'), float('inf'))
        evals[0] += 1
        try:
            r = evaluate_plan(graph, build(assign), 1, config)
            val = (r['makespan'], r['data_movement_bytes']['added_copy_bytes'])
        except Exception:
            val = (float('inf'), float('inf'))
        cache[key] = val
        return val

    def expired():
        return deadline is not None and time.perf_counter() >= deadline

    assign = {}
    for c, order in enumerate(seed_plan['core_schedules']):
        for s in order:
            assign[s] = c
    cur = ev(assign)
    if cur[0] == float('inf'):
        return None
    best_score = cur
    best_assign = dict(assign)
    if expired():
        return best_score[0], best_score[1], build(best_assign)
    hot = sorted(subs, key=lambda s: -bottleneck[s])[:top_t]
    for _ in range(max_iter):
        if evals[0] >= max_evals or expired():
            break
        cur = ev(assign)
        move = None
        for s in hot:
            if expired():
                break
            for c in range(n):
                if c == assign[s]:
                    continue
                if expired():
                    break
                na = dict(assign)
                na[s] = c
                v = ev(na)
                if v < cur and (move is None or v < move[0]):
                    move = (v, ('mv', s, c))
        if not expired():
            for ai in range(len(hot)):
                if expired():
                    break
                for bi in range(ai + 1, len(hot)):
                    if expired():
                        break
                    s1, s2 = hot[ai], hot[bi]
                    if assign[s1] == assign[s2]:
                        continue
                    na = dict(assign)
                    na[s1], na[s2] = assign[s2], assign[s1]
                    v = ev(na)
                    if v < cur and (move is None or v < move[0]):
                        move = (v, ('sw', s1, s2))
        if move is None:
            break
        _, act = move
        if act[0] == 'mv':
            assign[act[1]] = act[2]
        else:
            assign[act[1]], assign[act[2]] = assign[act[2]], assign[act[1]]
        best_score = move[0]
        best_assign = dict(assign)
        if expired():
            break
    if not expired():
        confirmed = ev(assign)
        if confirmed[0] != float('inf'):
            best_score = confirmed
            best_assign = dict(assign)
    return best_score[0], best_score[1], build(best_assign)
