"""可消融的文献启发优化。官方评价不变；关闭特性用于共同搜索框架对照。"""
from collections import defaultdict
import copy
import json
import math
import random
import time

from q1_solver import Graph, greedy_partition, multilevel, mutate, validate, topological

FEATURES = frozenset({'local_cost', 'critical', 'adaptive', 'portfolio'})
EXTRA_FEATURES = frozenset({'insertion', 'comm_rank', 'lookahead', 'calibrated', 'joint', 'budget_adapt', 'ddr', 'guarded_joint', 'beam', 'partition_guard', 'shared_input', 'local_repair'})


class CostGraph(Graph):
    def __init__(self, raw, settings, waits, enabled=False):
        super().__init__(raw, settings, waits)
        self.enabled = enabled
        self.local_observations = {}
        self.observation_conflicts = 0
        self.cost_hits = 0
        self.insertion = False
        self.beam = False
        self.placement_stats = []
        self.communication_rank = False
        self.calibrated = False
        self.learn_calibration = False
        self.ratios = defaultdict(list)

    def schedule(self, mapping, cores):
        if self.beam:
            from q1_beam import schedule
            plan, score, info = schedule(self, mapping, cores)
            self.placement_stats.append(info)
            return plan, score
        if self.insertion or self.communication_rank:
            from q1_insertion import schedule
            return schedule(self, mapping, cores, self.insertion, self.communication_rank)
        return super().schedule(mapping, cores)

    def observe(self, plan, result):
        groups = defaultdict(list)
        for u, s in plan['node_to_subgraph'].items():
            groups[s].append(int(u))
        mapping = {int(u): s for u, s in plan['node_to_subgraph'].items()}
        base = super().costs(mapping)[0] if self.calibrated or self.learn_calibration else {}
        for s, profile in result['step3_by_task'].items():
            key = tuple(sorted(groups[int(s)]))
            value = profile['local_makespan']
            if base and key not in self.local_observations and base[int(s)] > 0:
                loads = defaultdict(int)
                for u in key:
                    loads[self.ops[u]['pipe']] += self.ops[u]['cycles']
                pipe = max(loads, key=lambda p: (loads[p], p))
                self.ratios[pipe].append(max(.5, min(4., value/base[int(s)])))
            if key in self.local_observations and self.local_observations[key] != value:
                self.observation_conflicts += 1
            # Per-Graph cache: graph, hardware and official evaluator remain fixed.
            # This is a local estimate, never a cached concurrent task duration.
            self.local_observations[key] = value

    def costs(self, mapping):
        duration, traffic, view = super().costs(mapping)
        if not self.enabled:
            return duration, traffic, view
        groups = view[0]
        longest = {}
        for u in self.order:
            longest[u] = self.ops[u]['cycles'] + max(
                (longest[p] for p in self.pred[u] if mapping[p] == mapping[u]), default=0)
        for s, nodes in groups.items():
            key = tuple(sorted(nodes))
            if key in self.local_observations:
                duration[s] = self.local_observations[key]
                self.cost_hits += 1
            else:
                if self.calibrated:
                    from statistics import median
                    loads = defaultdict(int)
                    for u in nodes:
                        loads[self.ops[u]['pipe']] += self.ops[u]['cycles']
                    pipe = max(loads, key=lambda p: (loads[p], p))
                    if self.ratios[pipe]:
                        duration[s] *= median(self.ratios[pipe][-64:])
                duration[s] = max(duration[s], max((longest[u] for u in nodes), default=0))
        return duration, traffic, view


def task_slacks(g, plan, result):
    """冻结已观察的 Task 持续时间，反推数据/同核联合图的余量。

    DDR 竞争在方案改变后会变化，所以此余量只用于候选排序。
    """
    mapping = {int(u): s for u, s in plan['node_to_subgraph'].items()}
    groups, pred, succ, _ = g.view(mapping)
    pred = {s: set(v) for s, v in pred.items()}
    succ = {s: set(v) for s, v in succ.items()}
    owner = {s: c for c, seq in enumerate(plan['core_schedules']) for s in seq}
    delays = {(a, b): g.cross if owner[a] != owner[b] else 0
              for a in groups for b in succ[a]}
    for seq in plan['core_schedules']:
        for a, b in zip(seq, seq[1:]):
            pred[b].add(a)
            succ[a].add(b)
            delays[a, b] = max(g.same, delays.get((a, b), 0))
    tasks = {t['task_id']: t for c in result['per_core_timeline'] for t in c['tasks']}
    latest = {}
    for s in reversed(topological(pred, succ)):
        latest_end = min((latest[v] - delays[s, v] for v in succ[s]), default=result['makespan'])
        latest[s] = latest_end - tasks[s]['duration']
    return {s: max(0, latest[s] - tasks[s]['start']) for s in groups}


def adaptive_partition(g, cores, scale=1.0, max_nodes=256):
    """局部工作量/数据驻留代理驱动分组；不拆分或改写原始算子。"""
    total = defaultdict(int)
    for o in g.ops.values():
        total[o['pipe']] += o['cycles']
    target = max(g.cross, max(total.values(), default=0) * scale / max(1, cores * 8))
    # First obtain a communication-aware topological sequence using the old constructor.
    base = greedy_partition(g, cores, max_nodes)
    rank = {u: -base[u] for u in g.ops}
    order = topological(g.pred, g.succ, rank)
    mapping, block, count = {}, 0, 0
    loads, live, remaining = defaultdict(int), set(), {}
    resident = defaultdict(int)
    for u in order:
        if count >= max_nodes or (count >= 4 and (
                max(loads.values(), default=0) >= target or
                any(resident[p] > cap for p, cap in g.capacity.items()))):
            block += 1
            count = 0
            loads, live, remaining = defaultdict(int), set(), {}
            resident = defaultdict(int)
        mapping[u] = block
        count += 1
        loads[g.ops[u]['pipe']] += g.ops[u]['cycles']
        for i in g.incident[u]:
            size, pos, ps, cs, final = g.tensors[i]
            if i not in live:
                live.add(i)
                resident[pos] += size
                remaining[i] = set(cs)
            remaining[i].discard(u)
            # End-of-Task outputs stay resident in this conservative grouping proxy.
            if not remaining[i] and not final:
                live.remove(i)
                resident[pos] -= size
    return mapping


def directed_candidates(g, plan, result, cores, critical=False, adaptive=False, preserve=False):
    mapping = {int(u): s for u, s in plan['node_to_subgraph'].items()}
    groups, _, succ, order = g.view(mapping)
    tasks = [t for c in result['per_core_timeline'] for t in c['tasks']]
    slack = task_slacks(g, plan, result) if critical else {}
    tasks.sort(key=lambda t: (slack.get(t['task_id'], 0), -t['duration'], -t['end'], t['task_id']))
    for task in tasks[:4]:
        s = task['task_id']
        nodes = sorted(groups[s], key=g.pos.get)
        if len(nodes) > 1:
            weights = [g.ops[u]['cycles'] for u in nodes]
            total, prefix = sum(weights), 0
            choices = []
            for i, w in enumerate(weights[:-1], 1):
                prefix += w
                choices.append((abs(total / 2 - prefix), i))
            cut = min(choices)[1]
            cuts = [cut]
            if adaptive:
                # Favor low-traffic boundaries near a balanced work cut.
                def crossing(i):
                    left, right = set(nodes[:i]), set(nodes[i:])
                    tids = {t for u in nodes for t in g.incident[u]}
                    return sum(g.tensors[t][0] for t in tids
                               if g.tensors[t][2] & left and g.tensors[t][3] & right)
                nearby = range(max(1, cut - 3), min(len(nodes), cut + 4))
                cuts = sorted(set([cut, min(nearby, key=lambda i: (crossing(i), abs(i-cut), i))]))
            for i in cuts:
                trial = dict(mapping)
                for u in nodes[i:]:
                    trial[u] = max(groups) + 1
                try:
                    from q1_partition import repair
                    yield 'split', repair(g, plan, trial) if preserve else g.schedule(trial, cores)[0]
                except ValueError:
                    continue
        if adaptive:
            # Local merge alternatives retain the rest of the graph's granularity.
            for b in sorted(succ[s])[:2]:
                trial = {u: s if v == b else v for u, v in mapping.items()}
                try:
                    from q1_partition import repair
                    yield 'merge', repair(g, plan, trial) if preserve else g.schedule(trial, cores)[0]
                except ValueError:
                    continue
    positions = {s: i for i, s in enumerate(order)}
    finish = [max((t['end'] for t in c['tasks']), default=0) for c in result['per_core_timeline']]
    for task in tasks[:3]:
        s = task['task_id']
        source = next(i for i, seq in enumerate(plan['core_schedules']) if s in seq)
        for target in sorted(range(cores), key=lambda i: (finish[i], i)):
            if target == source:
                continue
            trial = copy.deepcopy(plan)
            trial['core_schedules'][source].remove(s)
            trial['core_schedules'][target].append(s)
            trial['core_schedules'][target].sort(key=positions.get)
            yield 'migrate', trial


def elite_update(entries, entry, limit=4):
    """非支配时间/搬运候选 + 最优时间兜底；只控制搜索存档，不作最优证明。"""
    pool = entries + [entry]
    pool.sort(key=lambda e: (e[0], json.dumps(e[1], sort_keys=True)))
    chosen = [pool[0]]
    for e in pool[1:]:
        if any(x[1] == e[1] for x in chosen):
            continue
        if not any(x[0][0] <= e[0][0] and x[0][1] <= e[0][1] and x[0] != e[0] for x in pool):
            chosen.append(e)
        if len(chosen) == limit:
            return chosen
    # Preserve structurally different runner-up solutions when the frontier is small.
    for e in pool:
        if len(chosen) == limit:
            break
        if not any(x[1]['node_to_subgraph'] == e[1]['node_to_subgraph'] for x in chosen):
            chosen.append(e)
    return chosen


def solve_experimental(raw, settings, waits, cores=4, evaluation_budget=12, seed=0,
                       features=(), on_evaluation=None, cache_dir=None):
    from multicore_cut_evaluate_problem_1 import evaluate_scene_a
    features = frozenset(features)
    if 'guarded_joint' in features and features & {'calibrated', 'joint', 'budget_adapt', 'ddr', 'portfolio', 'adaptive', 'lookahead'}:
        raise ValueError('guarded_joint must preserve the base search prefix; incompatible feature combination')
    if features - (FEATURES | EXTRA_FEATURES) or evaluation_budget < 1 or cores < 1:
        raise ValueError('未知特性或无效预算/核数')
    if features & {'shared_input', 'local_repair'} and 'partition_guard' not in features:
        raise ValueError('shared_input/local_repair require partition_guard')
    if 'partition_guard' in features and (evaluation_budget < 8 or features & {'guarded_joint', 'budget_adapt', 'portfolio', 'adaptive', 'joint', 'ddr', 'lookahead', 'beam', 'calibrated'}):
        raise ValueError('partition_guard requires budget >= 8 and base-only features')
    from q1_search_tools import EvaluationCache, replay, diagnose, ranked_joint, choose_arm
    g = CostGraph(raw, settings, waits, bool({'local_cost', 'calibrated'} & features))
    g.insertion = 'insertion' in features
    g.beam = 'beam' in features
    g.communication_rank = 'comm_rank' in features
    g.calibrated = 'calibrated' in features
    g.learn_calibration = 'guarded_joint' in features
    persistent = EvaluationCache(cache_dir, raw, settings, waits) if cache_dir else None
    started = time.perf_counter()
    rng = random.Random(seed)
    cache, history, rejected, archive = set(), [], [], []
    best = None

    def evaluate(plan, label):
        nonlocal best, archive
        key = json.dumps(plan, sort_keys=True)
        if key in cache or len(history) >= evaluation_budget:
            return None
        try:
            validate(g, plan)
        except (ValueError, RuntimeError) as exc:
            rejected.append({'candidate': label, 'reason': str(exc)})
            return None
        t = time.perf_counter()
        mapping = {int(u): s for u, s in plan['node_to_subgraph'].items()}
        predicted = replay(g, plan, g.costs(mapping)[0])
        def compute():
            return evaluate_scene_a(raw, plan, g.bandwidth, g.capacity, g.cross, g.same)
        result, cache_hit = persistent.run(plan, compute) if persistent else (compute(), False)
        diagnostic = diagnose(g, plan, result, predicted)
        score = (result['makespan'], result['data_movement_bytes']['added_copy_bytes'])
        entry = (score, plan, result)
        if best is None or score < best[0]:
            best = entry
        if 'portfolio' in features:
            archive = elite_update(archive, entry)
        else:
            archive = [best]
        if g.enabled:
            g.observe(plan, result)
        cache.add(key)
        history.append({'candidate': label, 'makespan': score[0], 'added_copy_bytes': score[1],
                        'evaluation_seconds': time.perf_counter() - t,
                        'cache_hit': cache_hit, 'timing_diagnostic': diagnostic,
                        'best_makespan': best[0][0]})
        if on_evaluation:
            on_evaluation(history[-1])
        return entry

    fallback = {'node_to_subgraph': {str(u): 0 for u in sorted(g.ops)},
                'core_schedules': [[0] if g.ops else []] + [[] for _ in range(cores-1)]}
    evaluate(fallback, 'single_task')
    baseline = best[0][0]
    if cores > 1 and len(history) < evaluation_budget:
        initial = greedy_partition(g, cores)
        evaluate(g.schedule(initial, cores)[0], 'greedy')
        if len(history) < evaluation_budget:
            coarse = multilevel(g, initial, cores)
            if 'shared_input' in features:
                from q1_partition import shared_coarsen
                coarse = shared_coarsen(g, coarse, cores)
            evaluate(g.schedule(coarse, cores)[0], 'multilevel')
    arms = ['grain', 'directed', 'random'] + (['local_reschedule'] if g.enabled else [])
    if 'budget_adapt' in features:
        arms = ['grain', 'directed', 'split', 'boundary', 'migrate', 'reorder', 'local_reschedule']
    if 'joint' in features:
        arms.append('joint')
    if 'ddr' in features:
        arms.append('ddr')
    queues = {}
    pulls, rewards = defaultdict(int), defaultdict(float)
    grain_index, directed, directed_key = 0, iter(()), None
    refreshes = 0
    protected_grain_attempts = []
    guarded_start = max(3, math.ceil(.75 * evaluation_budget))
    guarded_attempts = 0
    protected_score = None
    for attempt in range(evaluation_budget * 80 if cores > 1 else 0):
        if len(history) >= evaluation_budget:
            break
        if 'budget_adapt' in features:
            arm = choose_arm(arms, pulls, rewards, attempt)
        elif 'portfolio' in features:
            arm = next((a for a in arms if not pulls[a]), None)
            if arm is None:
                arm = max(arms, key=lambda a: (rewards[a] / pulls[a] +
                          math.sqrt(2 * math.log(1 + sum(pulls.values())) / pulls[a]), -arms.index(a)))
        else:
            arm = arms[attempt % len(arms)]
        if ('partition_guard' in features and grain_index < 4
                and evaluation_budget - len(history) <= 4 - grain_index):
            # Reserve only the remaining opportunities; retain normal ordering until needed.
            arm = 'grain'
        if 'guarded_joint' in features and len(history) >= guarded_start:
            if protected_score is None:
                protected_score = best[0][0]
            g.calibrated = True
            if guarded_attempts % 4 == 0:
                arm = 'joint'
            guarded_attempts += 1
        pulls[arm] += 1
        before = best[0][0]
        parent = archive[rng.randrange(len(archive))] if 'portfolio' in features and arm == 'random' else best
        label = arm
        try:
            if arm == 'grain':
                scales = [.5, 1., 2., .25, 4.]
                scale = scales[grain_index % len(scales)]
                grain_index += 1
                if 'partition_guard' in features and grain_index <= 4:
                    protected_grain_attempts.append(scale)
                mapping = (adaptive_partition(g, cores, scale) if 'adaptive' in features else
                           greedy_partition(g, cores, max(1, int(32 * scale))))
                trial = g.schedule(mapping, cores)[0]
                label = f'grain_{scale}'
            elif arm == 'directed':
                current_key = json.dumps(best[1], sort_keys=True)
                if directed_key is None or ('critical' in features and directed_key != current_key):
                    if 'lookahead' in features:
                        from itertools import chain
                        from q1_lookahead import candidates
                        directed = chain(candidates(g, best[1], best[2], cores),
                                         directed_candidates(g, best[1], best[2], cores,
                                                             'critical' in features, 'adaptive' in features, 'local_repair' in features))
                    else:
                        directed = directed_candidates(g, best[1], best[2], cores,
                                                       'critical' in features, 'adaptive' in features, 'local_repair' in features)
                    directed_key = current_key
                    refreshes += 1
                try:
                    kind, trial = next(directed)
                except StopIteration:
                    directed_key = None
                    continue
                label += '_' + kind
            elif arm == 'local_reschedule':
                trial = g.schedule({int(u): s for u, s in best[1]['node_to_subgraph'].items()}, cores)[0]
            elif arm in {'joint', 'ddr'}:
                current_key = json.dumps(best[1], sort_keys=True)
                if arm not in queues or queues[arm][0] != current_key:
                    queues[arm] = (current_key, ranked_joint(g, best[1], best[2], cores, arm == 'ddr'))
                try:
                    kind, trial = next(queues[arm][1])
                except StopIteration:
                    continue
                label += '_' + kind
            else:
                trial = parent[1]
                kind = arm if arm in {'split', 'boundary', 'migrate', 'reorder'} else rng.choice(['merge', 'split', 'boundary', 'migrate', 'reorder'])
                for _ in range(rng.randint(1, 3)):
                    trial = mutate(g, trial, cores, rng, kind, preserve='local_repair' in features)
                label += '_' + kind
        except (ValueError, RuntimeError) as exc:
            rejected.append({'candidate': label, 'reason': str(exc)})
            continue
        # Evaluator errors propagate. Only construction/legality failures are rejected above.
        entry = evaluate(trial, label)
        if entry:
            # Count-based reward keeps seeded runs reproducible across machine speeds.
            rewards[arm] += max(0., before - entry[0][0]) / max(1, baseline)
    stats = {'method': 'experimental', 'features': sorted(features), 'seed': seed,
             'evaluation_budget': evaluation_budget, 'evaluations': history,
             'official_calls': sum(not r['cache_hit'] for r in history),
             'cache_hits': sum(r['cache_hit'] for r in history),
             'budget_unit': 'unique evaluated candidates including cache hits; hits do not buy extra search',
             'shared_input_stats': getattr(g, 'shared_input_stats', {}),
             'protected_grain_attempts': protected_grain_attempts,
             'protected_prefix_evaluations': guarded_start if 'guarded_joint' in features else 0,
             'protected_prefix_makespan': protected_score,
             'budget_exhausted': len(history) == evaluation_budget,
             'singlecore_makespan': baseline, 'speedup': baseline / best[0][0] if best[0][0] else 1.,
             'rejected_proposals': rejected, 'local_cost_entries': len(g.local_observations),
             'local_cost_hits': g.cost_hits, 'local_cost_conflicts': g.observation_conflicts,
             'placement_stats': g.placement_stats,
             'critical_refreshes': refreshes, 'arm_pulls': dict(pulls), 'arm_rewards': dict(rewards),
             'elite_scores': [e[0] for e in archive], 'elapsed_seconds': time.perf_counter() - started}
    return best[1], best[2], stats
