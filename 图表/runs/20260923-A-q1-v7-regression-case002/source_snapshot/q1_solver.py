"""问题一初版：贪心融合、多层次有向超图粗化/细化、ALNS。

估计模型只负责生成候选，最终选择始终使用未修改的官方评估器。
"""
from collections import defaultdict
import copy
import heapq
import json
import math
import random
import time


def topological(pred, succ, priority=None):
    degree = {u: len(p) for u, p in pred.items()}
    ready = [(0 if priority is None else -priority[u], u) for u in pred if not degree[u]]
    heapq.heapify(ready)
    order = []
    while ready:
        _, u = heapq.heappop(ready)
        order.append(u)
        for v in sorted(succ[u]):
            degree[v] -= 1
            if degree[v] == 0:
                heapq.heappush(ready, (0 if priority is None else -priority[v], v))
    if len(order) != len(pred):
        raise ValueError('子图收缩或执行顺序产生环')
    return order


class Graph:
    def __init__(self, graph, settings, waits):
        from evaluation_validation import validate_graph
        from stub_multicore_cut_and_schedule import _build_op_adjacency, _contract_excluded_copy_nodes
        validate_graph(graph)
        self.raw = graph
        self.ops = {o['id']: o for o in graph['ops'] if o['op'] not in {'COPY_IN', 'COPY_OUT'}}
        _, full = _build_op_adjacency(graph)
        self.pred, self.succ = _contract_excluded_copy_nodes(sorted(self.ops), full)
        self.order = topological(self.pred, self.succ)
        self.pos = {u: i for i, u in enumerate(self.order)}
        self.bandwidth = settings['bandwidth']
        self.capacity = settings['capacity']
        self.cross = waits['task_cross_core_wait_cycles']
        self.same = waits['task_same_core_wait_cycles']
        all_ops = {o['id']: o for o in graph['ops']}
        producers, consumers = defaultdict(set), defaultdict(set)
        for e in graph['edges']:
            a, b = e['source'], e['target']
            if a in all_ops and b not in all_ops:
                producers[b].add(a)
            elif a not in all_ops and b in all_ops:
                consumers[a].add(b)
        self.tensors = []
        self.incident = defaultdict(list)
        for t in graph['tensors']:
            ps = producers[t['id']] & self.ops.keys()
            cs = consumers[t['id']] & self.ops.keys()
            if not ps and not cs:
                continue
            final = any(all_ops[u]['op'] == 'COPY_OUT' for u in consumers[t['id']])
            item = (t['size'], 'UB' if t['pos'] == 'DDR' else t['pos'], ps, cs, final)
            index = len(self.tensors)
            self.tensors.append(item)
            for u in ps | cs:
                self.incident[u].append(index)
        self.rank = {}
        for u in reversed(self.order):
            self.rank[u] = self.ops[u]['cycles'] + max((self.rank[v] for v in self.succ[u]), default=0)

    def view(self, mapping):
        if set(mapping) != set(self.ops):
            raise ValueError('算子覆盖不完整')
        groups = defaultdict(set)
        for u, s in mapping.items():
            groups[s].add(u)
        pred = {s: set() for s in groups}
        succ = {s: set() for s in groups}
        for u in self.order:
            for v in self.succ[u]:
                a, b = mapping[u], mapping[v]
                if a != b:
                    succ[a].add(b)
                    pred[b].add(a)
        order = topological(pred, succ)
        return groups, pred, succ, order

    def costs(self, mapping):
        """四 Pipe 负载、按 tensor/子图去重的边界流量和活跃集压力代理。"""
        groups, pred, succ, order = self.view(mapping)
        loads = {s: defaultdict(float) for s in groups}
        events = {s: defaultdict(lambda: defaultdict(int)) for s in groups}
        traffic = 0
        for u, s in mapping.items():
            loads[s][self.ops[u]['pipe']] += self.ops[u]['cycles']
        for size, pos, ps, cs, final in self.tensors:
            pg, cg = {mapping[u] for u in ps}, {mapping[u] for u in cs}
            for s in sorted(pg | cg):
                local_p, local_c = ps & groups[s], cs & groups[s]
                incoming = bool(local_c) and not local_p
                outgoing = bool(local_p) and (final or not cs or bool(cs - groups[s]))
                if incoming:
                    loads[s]['PIPE_MTE2'] += math.ceil(size / self.bandwidth)
                    traffic += size
                if outgoing:
                    loads[s]['PIPE_MTE3'] += math.ceil(size / self.bandwidth)
                    traffic += size
                uses = [self.pos[u] for u in local_p | local_c]
                # 原图拓扑顺序上的存活区间，仅作压力代理；实际溢出由官方处理。
                events[s][min(uses)][pos] += size
                events[s][max(uses) + 1][pos] -= size
        duration = {}
        for s in groups:
            live, peak = defaultdict(int), defaultdict(int)
            for i in sorted(events[s]):
                for pos, delta in events[s][i].items():
                    live[pos] += delta
                    peak[pos] = max(peak[pos], live[pos])
            pressure = sum(max(0, peak[p] - cap) for p, cap in self.capacity.items())
            duration[s] = max(loads[s].values(), default=0) + 2 * pressure / self.bandwidth
        return duration, traffic, (groups, pred, succ, order)

    def schedule(self, mapping, cores):
        duration, traffic, (_, pred, succ, order) = self.costs(mapping)
        rank = {}
        for s in reversed(order):
            rank[s] = duration[s] + max((self.same + rank[v] for v in succ[s]), default=0)
        end, assigned, free = {}, {}, [None] * cores
        schedules = [[] for _ in range(cores)]
        for s in topological(pred, succ, rank):
            options = []
            for c in range(cores):
                start = 0 if free[c] is None else free[c] + self.same
                for p in pred[s]:
                    start = max(start, end[p] + (self.cross if assigned[p] != c else 0))
                options.append((start + duration[s], c))
            finish, c = min(options)
            end[s], assigned[s], free[c] = finish, c, finish
            schedules[c].append(s)
        plan = {'node_to_subgraph': {str(u): mapping[u] for u in sorted(mapping)},
                'core_schedules': schedules}
        proxy = max(max(end.values(), default=0), traffic / self.bandwidth)
        return plan, proxy


def greedy_partition(g, cores, block_size=64):
    """按全局就绪集构造拓扑连续块，优先融合具有数据复用的节点。"""
    degree = {u: len(g.pred[u]) for u in g.ops}
    ready = {u for u in g.ops if degree[u] == 0}
    heap = [(-g.rank[u], u) for u in ready]
    heapq.heapify(heap)
    mapping, block = {}, 0
    target = max(1, min(block_size, math.ceil(len(g.ops) / max(1, 4 * cores))))
    while ready:
        touched, frontier = set(), set()
        for _ in range(target):
            if not ready:
                break
            candidates = frontier & ready
            def score(u):
                reuse = sum(g.tensors[i][0] for i in g.incident[u] if i in touched)
                return (reuse / g.bandwidth + g.same, g.rank[u], -u)
            if candidates:
                u = max(candidates, key=score)
            else:
                while heap and heap[0][1] not in ready:
                    heapq.heappop(heap)
                _, u = heapq.heappop(heap)
            ready.remove(u)
            touched.update(g.incident[u])
            frontier.discard(u)
            for i in g.incident[u]:
                _, _, ps, cs, _ = g.tensors[i]
                frontier.update(v for v in ps | cs if v not in mapping)
            mapping[u] = block
            for v in sorted(g.succ[u]):
                degree[v] -= 1
                if degree[v] == 0:
                    ready.add(v)
                    heapq.heappush(heap, (-g.rank[v], v))
        block += 1
    return mapping


def multilevel(g, initial, cores, levels=3):
    """有向超图粗化，保存层次，再以近似调度代价选择性展开细化。"""
    mapping = dict(initial)
    hierarchy = []
    for _ in range(levels):
        groups, pred, succ, _ = g.view(mapping)
        affinity = defaultdict(float)
        for size, _, ps, cs, _ in g.tensors:
            producers = {mapping[u] for u in ps}
            consumers = {mapping[u] for u in cs}
            for a in producers:
                for b in consumers - {a}:
                    affinity[a, b] += size
        used = set()
        accepted = 0
        for (a, b), weight in sorted(affinity.items(), key=lambda x: (-x[1], x[0])):
            if a in used or b in used or len(groups[a]) + len(groups[b]) > 1024:
                continue
            trial = {u: a if s == b else s for u, s in mapping.items()}
            try:
                g.view(trial)
            except ValueError:
                continue
            hierarchy.append((a, b, set(groups[b])))
            mapping = trial
            used.update((a, b))
            accepted += 1
            if accepted >= 32:
                break
        if not accepted:
            break
    _, current = g.schedule(mapping, cores)
    # Reverse contractions ensure a later parent merge is undone before its child.
    # If a parent stays merged, skip the child (its saved membership is no longer whole).
    for a, b, members in reversed(hierarchy):
        if any(mapping[u] != a for u in members):
            continue
        trial = dict(mapping)
        for u in members:
            trial[u] = b
        try:
            _, value = g.schedule(trial, cores)
        except ValueError:
            continue
        if value < current:
            mapping, current = trial, value
    return mapping


def validate(g, plan):
    from stub_multicore_cut_and_schedule import derive_multicore_plan
    from evaluation_validation import validate_task_order
    validate_task_order(derive_multicore_plan(g.raw, plan))


def mutate(g, plan, cores, rng, kind):
    trial = copy.deepcopy(plan)
    mapping = {int(u): s for u, s in plan['node_to_subgraph'].items()}
    groups, pred, succ, order = g.view(mapping)
    if not groups:
        return trial
    if kind == 'merge':
        pairs = [(a, b) for a in sorted(succ) for b in sorted(succ[a])]
        if not pairs:
            return trial
        a, b = rng.choice(pairs)
        mapping = {u: a if s == b else s for u, s in mapping.items()}
    elif kind == 'split':
        choices = [s for s in sorted(groups) if len(groups[s]) > 1]
        if not choices:
            return trial
        s = rng.choice(choices)
        nodes = sorted(groups[s], key=g.pos.get)
        cut = rng.randrange(1, len(nodes))
        for u in nodes[cut:]:
            mapping[u] = max(groups) + 1
    elif kind == 'boundary':
        edges = [(u, v) for u in g.order for v in sorted(g.succ[u]) if mapping[u] != mapping[v]]
        if not edges:
            return trial
        u, v = rng.choice(edges)
        if rng.random() < .5:
            mapping[u] = mapping[v]
        else:
            mapping[v] = mapping[u]
    elif kind == 'migrate':
        s = rng.choice(sorted(groups))
        for seq in trial['core_schedules']:
            if s in seq:
                seq.remove(s)
        target = trial['core_schedules'][rng.randrange(cores)]
        # Project a common topological ordering; official validation checks extra core edges.
        position = {v: i for i, v in enumerate(order)}
        target.append(s)
        target.sort(key=position.get)
        return trial
    else:
        choices = [seq for seq in trial['core_schedules'] if len(seq) > 1]
        if choices:
            seq = rng.choice(choices)
            i = rng.randrange(len(seq) - 1)
            seq[i], seq[i + 1] = seq[i + 1], seq[i]
        return trial
    return g.schedule(mapping, cores)[0]


def bottleneck_candidates(g, plan, result, cores):
    """按真实 Task 持续时间选拆分对象，并尝试将长 Task 移到较早结束的核。"""
    mapping = {int(u): s for u, s in plan['node_to_subgraph'].items()}
    groups, _, _, order = g.view(mapping)
    tasks = sorted((t for c in result['per_core_timeline'] for t in c['tasks']),
                   key=lambda t: (-t['duration'], -t['end'], t['task_id']))
    for task in tasks[:4]:
        s = task['task_id']
        nodes = sorted(groups[s], key=g.pos.get)
        if len(nodes) < 2:
            continue
        # Balance the dominant compute Pipe, rather than splitting by op count.
        loads = defaultdict(int)
        for u in nodes:
            loads[g.ops[u]['pipe']] += g.ops[u]['cycles']
        pipe = max(loads, key=lambda p: (loads[p], p))
        partial = 0
        cuts = []
        for i, u in enumerate(nodes[:-1], 1):
            if g.ops[u]['pipe'] == pipe:
                partial += g.ops[u]['cycles']
            cuts.append((abs(loads[pipe] / 2 - partial), i))
        _, cut = min(cuts)
        trial = dict(mapping)
        for u in nodes[cut:]:
            trial[u] = max(groups) + 1
        try:
            yield 'critical_split', g.schedule(trial, cores)[0]
        except ValueError:
            continue
    finish = [max((t['end'] for t in c['tasks']), default=0) for c in result['per_core_timeline']]
    positions = {s: i for i, s in enumerate(order)}
    for task in tasks[:3]:
        s = task['task_id']
        source = next(i for i, seq in enumerate(plan['core_schedules']) if s in seq)
        for target in sorted(range(cores), key=lambda c: (finish[c], c)):
            if source == target:
                continue
            trial = copy.deepcopy(plan)
            trial['core_schedules'][source].remove(s)
            trial['core_schedules'][target].append(s)
            trial['core_schedules'][target].sort(key=positions.get)
            yield 'critical_migrate', trial


def solve(g, cores=4, method='alns', budget=12, seed=0, block_size=64, on_evaluation=None,
          refine_budget=0):
    """budget 是 ALNS 新候选的官方评估次数上限；初解另计。"""
    from multicore_cut_evaluate_problem_1 import evaluate_scene_a
    if cores < 1 or budget < 0 or block_size < 1 or refine_budget < 0:
        raise ValueError('cores/block_size 必须为正，budget 不得为负')
    if method not in {'greedy', 'multilevel', 'alns'}:
        raise ValueError('未知方法')
    rng = random.Random(seed)
    cache, records, failures = {}, [], []
    started = time.perf_counter()

    def evaluate(plan, label):
        key = json.dumps(plan, sort_keys=True)
        if key in cache:
            return cache[key], None
        validate(g, plan)
        t = time.perf_counter()
        result = evaluate_scene_a(g.raw, plan, g.bandwidth, g.capacity, g.cross, g.same)
        score = (result['makespan'], result['data_movement_bytes']['added_copy_bytes'])
        # Full official traces can be large; retain only scores for rejected candidates.
        cache[key] = score
        records.append({'candidate': label, 'makespan': score[0], 'added_copy_bytes': score[1],
                        'evaluation_seconds': time.perf_counter() - t})
        if on_evaluation is not None:
            on_evaluation(records[-1])
        return score, result

    # Always keep the single-Task fallback: using available cores must not force a regression.
    fallback = {'node_to_subgraph': {str(u): 0 for u in sorted(g.ops)},
                'core_schedules': [[0] if g.ops else []] + [[] for _ in range(cores - 1)]}
    best = fallback
    best_score, best_result = evaluate(best, 'single_task')
    single_time = best_score[0]
    initial = greedy_partition(g, cores, block_size) if cores > 1 else {}
    candidates = [('greedy', g.schedule(initial, cores)[0])] if cores > 1 else []
    if cores > 1 and method in {'multilevel', 'alns'}:
        candidates.append(('multilevel', g.schedule(multilevel(g, initial, cores), cores)[0]))
    for label, candidate in candidates:
        score, result = evaluate(candidate, label)
        if score < best_score:
            best, best_score, best_result = candidate, score, result
    current, current_score = best, best_score
    kinds = ['merge', 'split', 'boundary', 'migrate', 'reorder']
    weights = [1.0] * len(kinds)
    evaluated = 0
    if method == 'alns' and cores > 1:
        for attempt in range(max(20, budget * 20)):
            if evaluated >= budget:
                break
            k = rng.choices(range(len(kinds)), weights=weights)[0]
            kind = kinds[k]
            try:
                trial = current
                # Compound destroy/repair of a small region, followed by list-schedule repair.
                # Initial prototype uses 1--3 edits; not a whole-graph random restart.
                for _ in range(rng.randint(1, 3)):
                    trial = mutate(g, trial, cores, rng, kind)
                key = json.dumps(trial, sort_keys=True)
                if key in cache:
                    continue
                validate(g, trial)
            except (ValueError, RuntimeError) as exc:
                failures.append({'operation': kind, 'reason': str(exc)})
                continue
            # Evaluator failures propagate: implementation bugs must not look like bad candidates.
            score, result = evaluate(trial, kind)
            evaluated += 1
            improved = score < best_score
            temp = max(1.0, single_time * .03 * (1 - evaluated / max(1, budget)))
            if score < current_score or rng.random() < math.exp(min(0, (current_score[0] - score[0]) / temp)):
                current, current_score = trial, score
            if improved:
                best, best_score, best_result = trial, score, result
            weights[k] = .8 * weights[k] + .2 * (5 if improved else 1)
    # Optional non-regressing refinement, separately budgeted for honest comparisons.
    refinement_evaluations = 0
    if cores > 1 and refine_budget:
        from itertools import chain
        sizes = sorted({max(1, block_size // 4), max(1, block_size // 2), block_size * 2})
        granular = ((f'granularity_{size}', g.schedule(greedy_partition(g, cores, size), cores)[0])
                    for size in sizes)
        pending = chain(granular, bottleneck_candidates(g, best, best_result, cores))
        for _ in range(refine_budget * 20):
            if refinement_evaluations >= refine_budget:
                break
            try:
                label, trial = next(pending)
            except StopIteration:
                break
            if json.dumps(trial, sort_keys=True) in cache:
                continue
            try:
                validate(g, trial)
            except (ValueError, RuntimeError) as exc:
                failures.append({'operation': label, 'reason': str(exc)})
                continue
            score, result = evaluate(trial, label)
            refinement_evaluations += 1
            if score < best_score:
                best, best_score, best_result = trial, score, result
                # Recompute the bottleneck after improvement; retain untried granular candidates.
                pending = chain(pending, bottleneck_candidates(g, best, best_result, cores))
    return best, best_result, {'method': method, 'seed': seed, 'budget': budget,
            'refine_budget': refine_budget, 'refinement_evaluations': refinement_evaluations,
            'block_size': block_size, 'singlecore_makespan': single_time,
            'speedup': single_time / best_score[0] if best_score[0] else 1.0,
            'search_evaluations': evaluated, 'evaluations': records,
            'rejected_proposals': failures, 'operator_weights': dict(zip(kinds, weights)),
            'elapsed_seconds': time.perf_counter() - started}
