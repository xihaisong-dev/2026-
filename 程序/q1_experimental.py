"""可消融的文献启发优化。官方评价不变；关闭特性用于共同搜索框架对照。"""
from collections import defaultdict
import copy
import json
import math
import random
import time

from q1_solver import Graph, greedy_partition, multilevel, mutate, validate, topological

FEATURES = frozenset({'local_cost', 'critical', 'adaptive', 'portfolio'})
EXTRA_FEATURES = frozenset({'insertion', 'comm_rank', 'lookahead', 'calibrated', 'joint', 'budget_adapt', 'ddr', 'guarded_joint', 'beam', 'partition_guard', 'shared_input', 'local_repair', 'repair_move', 'region', 'region_gap', 'fluid_rank', 'boundary_refine', 'exact_region', 'wide_region', 'uphill_region', 'phase_rank', 'event_rank', 'chain_joint', 'late_chain', 'resource_init', 'init_components', 'init_batches', 'init_depth', 'component_guard', 'component_slot', 'component_followup', 'component_local_rank', 'memory_route', 'hybrid_route', 'fast_contractions'})


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
        self.guided_repair_stats = []
        self.region_stats = []
        self.boundary_stats = []
        self.chain_stats = []
        self.communication_rank = False
        self.calibrated = False
        self.learn_calibration = False
        self.ratios = defaultdict(list)
        self.fast_costs = False

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
        if self.fast_costs:
            from q1_fast_costs import costs
            duration, traffic, view = costs(self, mapping)
        else:
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
                    from q1_guided_repair import guided_repair
                    yield 'split', (guided_repair(g, plan, trial, cores) if preserve == 'mobile' else
                                    repair(g, plan, trial) if preserve else g.schedule(trial, cores)[0])
                except ValueError:
                    continue
        if adaptive:
            # Local merge alternatives retain the rest of the graph's granularity.
            for b in sorted(succ[s])[:2]:
                trial = {u: s if v == b else v for u, v in mapping.items()}
                try:
                    from q1_partition import repair
                    from q1_guided_repair import guided_repair
                    yield 'merge', (guided_repair(g, plan, trial, cores) if preserve == 'mobile' else
                                    repair(g, plan, trial) if preserve else g.schedule(trial, cores)[0])
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
                       features=(), on_evaluation=None, cache_dir=None, single_reference=None,
                       evaluator_backend='official', on_proposal=None):
    from multicore_cut_evaluate_problem_1 import evaluate_scene_a
    if evaluator_backend == 'counter':
        from q1_fast_evaluator import evaluate_scene_a, BACKEND_ID
        # Keep derived-backend evidence separate from the original cache.
        if cache_dir is not None:
            from pathlib import Path
            cache_dir = Path(cache_dir) / BACKEND_ID.replace(':', '-')
    elif evaluator_backend != 'official':
        raise ValueError('Unknown evaluator backend')
    features = frozenset(features)
    if 'late_chain' in features and 'chain_joint' not in features:
        raise ValueError('late_chain requires chain_joint')
    if 'chain_joint' in features and 'event_rank' not in features:
        raise ValueError('chain_joint requires event_rank')
    if 'event_rank' in features and features & {'phase_rank','wide_region','uphill_region'}:
        raise ValueError('event_rank must be an isolated ablation')
    if features & {'wide_region', 'uphill_region', 'phase_rank', 'event_rank'} and 'exact_region' not in features:
        raise ValueError('wide/uphill region require exact_region')
    if 'exact_region' in features and ('region' not in features or features & {'fluid_rank','boundary_refine','region_gap'}):
        raise ValueError('exact_region requires region and isolated ranking')
    if 'guarded_joint' in features and features & {'calibrated', 'joint', 'budget_adapt', 'ddr', 'portfolio', 'adaptive', 'lookahead'}:
        raise ValueError('guarded_joint must preserve the base search prefix; incompatible feature combination')
    if features - (FEATURES | EXTRA_FEATURES) or evaluation_budget < 1 or cores < 1:
        raise ValueError('未知特性或无效预算/核数')
    if features & {'shared_input', 'local_repair', 'repair_move', 'region'} and 'partition_guard' not in features:
        raise ValueError('shared_input/local_repair/repair_move require partition_guard')
    if features & {'fluid_rank', 'boundary_refine'} and ('region' not in features or 'region_gap' in features):
        raise ValueError('fluid_rank/boundary_refine require region and exclude region_gap for isolated ablation')
    if 'region_gap' in features and 'region' not in features:
        raise ValueError('region_gap requires region')
    if 'region' in features and ('local_cost' not in features or features & {'local_repair', 'repair_move'}):
        raise ValueError('region requires local_cost and excludes other repair modes')
    if {'local_repair', 'repair_move'} <= features:
        raise ValueError('Choose local_repair or repair_move, not both')
    if 'partition_guard' in features and (evaluation_budget < 8 or features & {'guarded_joint', 'budget_adapt', 'portfolio', 'adaptive', 'joint', 'ddr', 'lookahead', 'beam', 'calibrated'}):
        raise ValueError('partition_guard requires budget >= 8 and base-only features')
    structural = features & {'init_components', 'init_batches', 'init_depth'}
    if structural and ('partition_guard' not in features or evaluation_budget < 12 or 'resource_init' in features):
        raise ValueError('Structural seeds require partition_guard, budget >= 12 and exclude resource_init')
    if features & {'component_guard', 'component_slot'} and (structural != {'init_components'} or 'component_guard' not in features):
        raise ValueError('Component routing requires only init_components and component_guard')
    if features & {'memory_route','hybrid_route'} and ('component_local_rank' not in features or {'memory_route','hybrid_route'} <= features):
        raise ValueError('Choose one route with component_local_rank')
    if 'component_local_rank' in features and 'component_followup' not in features:
        raise ValueError('component_local_rank requires component_followup')
    if 'component_followup' in features and 'component_slot' not in features:
        raise ValueError('component_followup requires component_slot')
    from q1_search_tools import EvaluationCache, replay, diagnose, ranked_joint, choose_arm
    g = CostGraph(raw, settings, waits, bool({'local_cost', 'calibrated'} & features))
    g.fast_costs = evaluator_backend == 'counter'
    g.fast_contractions = 'fast_contractions' in features
    g.insertion = 'insertion' in features
    g.beam = 'beam' in features
    g.communication_rank = 'comm_rank' in features
    g.calibrated = 'calibrated' in features
    g.learn_calibration = 'guarded_joint' in features
    persistent = EvaluationCache(cache_dir, raw, settings, waits) if cache_dir else None
    started = time.perf_counter()
    rng = random.Random(seed)
    cache, history, rejected, archive = {}, [], [], []
    proposal_ledger = []
    protected_grain_ledger = []
    best = None

    def evaluate(plan, label, observe_improving_only=False):
        nonlocal best, archive
        if on_proposal is not None:
            on_proposal(copy.deepcopy(plan), label)
        key = json.dumps(plan, sort_keys=True)
        import hashlib
        record = {'candidate': label, 'plan_sha256': hashlib.sha256(key.encode()).hexdigest()}
        proposal_ledger.append(record)
        if key in cache:
            record.update(status='duplicate', evaluation_id=cache[key])
            return None
        if len(history) >= evaluation_budget:
            record['status'] = 'budget_exhausted'
            return None
        try:
            validate(g, plan)
        except (ValueError, RuntimeError) as exc:
            rejected.append({'candidate': label, 'reason': str(exc)})
            record.update(status='infeasible', reason=str(exc))
            return None
        t = time.perf_counter()
        mapping = {int(u): s for u, s in plan['node_to_subgraph'].items()}
        predicted = replay(g, plan, g.costs(mapping)[0])
        def compute():
            return evaluate_scene_a(raw, plan, g.bandwidth, g.capacity, g.cross, g.same)
        if label == 'single_task' and single_reference is not None:
            from q1_single_reference import reuse
            result = reuse(single_reference, raw, settings, waits, cores)
            cache_hit = True
        else:
            result, cache_hit = persistent.run(plan, compute) if persistent else (compute(), False)
        diagnostic = diagnose(g, plan, result, predicted)
        score = (result['makespan'], result['data_movement_bytes']['added_copy_bytes'])
        entry = (score, plan, result)
        improved = best is None or score < best[0]
        if improved:
            best = entry
        if 'portfolio' in features:
            archive = elite_update(archive, entry)
        else:
            archive = [best]
        if g.enabled and (not observe_improving_only or improved):
            g.observe(plan, result)
        if observe_improving_only:
            record['cost_observation_applied'] = bool(g.enabled and improved)
        cache[key] = len(history)
        record.update(status='evaluated', evaluation_id=len(history), cache_hit=cache_hit)
        history.append({'candidate': label, 'makespan': score[0], 'added_copy_bytes': score[1],
                        'evaluation_seconds': time.perf_counter() - t,
                        'cache_hit': cache_hit, 'fixed_single_reference': label == 'single_task' and single_reference is not None,
                        'timing_diagnostic': diagnostic,
                        'best_makespan': best[0][0]})
        if on_evaluation:
            on_evaluation(history[-1])
        return entry

    fallback = {'node_to_subgraph': {str(u): 0 for u in sorted(g.ops)},
                'core_schedules': [[0] if g.ops else []] + [[] for _ in range(cores-1)]}
    evaluate(fallback, 'single_task')
    baseline = best[0][0]
    if cores > 1 and len(history) < evaluation_budget:
        if 'resource_init' in features:
            from q1_resource_init import resource_partition
            initial = resource_partition(g, cores)
        else:
            initial = greedy_partition(g, cores)
        evaluate(g.schedule(initial, cores)[0], 'resource_initial' if 'resource_init' in features else 'greedy')
        if len(history) < evaluation_budget:
            coarse = multilevel(g, initial, cores)
            if 'shared_input' in features:
                from q1_partition import shared_coarsen
                coarse = shared_coarsen(g, coarse, cores)
            evaluate(g.schedule(coarse, cores)[0], 'multilevel')
    structural_info = {}
    pending_component = []
    followup_unlocked = False
    if structural and cores > 1:
        from q1_structural_seeds import initial_candidates, canonical_key
        if 'component_guard' in features:
            from q1_structural_seeds import guarded_component_candidate
            if features & {'memory_route','hybrid_route'}:
                from q1_memory_routes import routed_candidates
                proposals, structural_info = routed_candidates(raw, settings, waits, cores, 'memory' if 'memory_route' in features else 'hybrid')
            elif 'component_local_rank' in features:
                proposals, structural_info = guarded_component_candidate(raw, settings, waits, cores, max_candidates=2, ranking='local')
            elif 'component_followup' in features:
                proposals, structural_info = guarded_component_candidate(raw, settings, waits, cores, max_candidates=2)
            else:
                proposals, structural_info = guarded_component_candidate(raw, settings, waits, cores)
        else:
            proposals, structural_info = initial_candidates(raw, settings, waits, cores,
                {feature.removeprefix('init_') for feature in structural})
        # At most four new official opportunities. Four grain attempts and at
        # least one normal search opportunity survive, in addition to old init.
        limit = max(0, min(4, evaluation_budget - len(history) - 5))
        if 'component_guard' in features:
            limit = min(limit, 2 if 'component_followup' in features else 1)
        structural_info.update(limit=limit, evaluated=0, ledger=[])
        if 'component_slot' in features:
            pending_component = proposals
            proposals = []
        known = {canonical_key(json.loads(key)): index for key, index in cache.items()}
        for kind, plan in proposals:
            record = {'candidate': 'structural_' + kind}
            structural_info['ledger'].append(record)
            key = canonical_key(plan)
            if key in known:
                record.update(status='equivalent_duplicate', evaluation_id=known[key])
                continue
            if structural_info['evaluated'] >= limit:
                record['status'] = 'seed_limit'
                continue
            if 'component_guard' in features and structural_info['selected_compute_lower_bound'] > best[0][0]:
                record['status'] = 'compute_bound_exceeds_incumbent'
                continue
            entry = evaluate(plan, record['candidate'], observe_improving_only='component_guard' in features)
            record.update(proposal_ledger[-1])
            if entry:
                structural_info['evaluated'] += 1
                known[key] = len(history) - 1
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
    region_attempts = 0
    late_region_start = None
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
                and evaluation_budget - len(history) <= 4 - grain_index + int('late_chain' in features and region_attempts == 0)):
            # Reserve only the remaining opportunities; retain normal ordering until needed.
            arm = 'grain'
        if 'late_chain' in features and region_attempts == 0 and grain_index >= 4 and len(history) == evaluation_budget-1:
            arm = 'random'
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
        grain_record = None
        try:
            if arm == 'grain':
                scales = [.5, 1., 2., .25, 4.]
                scale = scales[grain_index % len(scales)]
                grain_index += 1
                if 'partition_guard' in features and grain_index <= 4:
                    protected_grain_attempts.append(scale)
                    grain_record = {'scale': scale, 'status': 'constructing'}
                    protected_grain_ledger.append(grain_record)
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
                                                             'critical' in features, 'adaptive' in features, ('mobile' if 'repair_move' in features else 'local_repair' in features)))
                    else:
                        directed = directed_candidates(g, best[1], best[2], cores,
                                                       'critical' in features, 'adaptive' in features, ('mobile' if 'repair_move' in features else 'local_repair' in features))
                    directed_key = current_key
                    refreshes += 1
                try:
                    kind, trial = next(directed)
                except StopIteration:
                    directed_key = None
                    continue
                label += '_' + kind
            elif (arm == 'random' and 'region' in features and region_attempts < 1
                  and (pulls['random'] >= 2 or 'late_chain' in features)
                  and ('late_chain' not in features or len(history) == evaluation_budget-1)):
                if 'late_chain' in features:
                    late_region_start = {'evaluation_index':len(history), 'grain_attempts':list(protected_grain_attempts), 'incumbent_time':best[0][0]}
                from q1_region import candidates as region_candidates
                region_attempts += 1
                current_key = json.dumps(best[1], sort_keys=True)
                if 'region' not in queues or queues['region'][0] != current_key:
                    if 'exact_region' in features:
                        from q1_ranked_region import ranked_candidates
                        queue = ranked_candidates(g, raw, best[1], best[2], cores, 'wide_region' in features, 'uphill_region' in features, 'phase_rank' in features, 'event_rank' in features, 'chain_joint' in features)
                    elif features & {'fluid_rank', 'boundary_refine'}:
                        from q1_boundary_refine import ranked_candidates
                        queue = ranked_candidates(g, best[1], best[2], cores, 'fluid_rank' in features, 'boundary_refine' in features)
                    else:
                        queue = region_candidates(g, best[1], best[2], cores, 'region_gap' in features)
                    queues['region'] = (current_key, queue)
                try:
                    kind, trial = next(queues['region'][1])
                except StopIteration:
                    continue
                label = 'region_' + kind
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
                    trial = mutate(g, trial, cores, rng, kind, preserve=('mobile' if 'repair_move' in features else 'local_repair' in features))
                label += '_' + kind
        except (ValueError, RuntimeError) as exc:
            rejected.append({'candidate': label, 'reason': str(exc)})
            if grain_record is not None:
                grain_record.update(status='infeasible', reason=str(exc))
            continue
        # Evaluator errors propagate. Only construction/legality failures are rejected above.
        entry = None
        # Construct the original random proposal first, preserving RNG draws.
        # A structural probe replaces one ordinary random opportunity, not a
        # directed/grain/local-reschedule/region opportunity.
        ordinary_random = arm == 'random' and not label.startswith('region_')
        duplicate_opportunity = False
        if pending_component and followup_unlocked:
            known = {canonical_key(json.loads(key)): index for key, index in cache.items()}
            duplicate_opportunity = canonical_key(trial) in known
        if pending_component and (ordinary_random or duplicate_opportunity):
            kind, component_plan = pending_component.pop(0)
            record = {'candidate': 'structural_' + kind, 'replaces_candidate': label}
            if 'component_followup' in features:
                record.update(probe_index=structural_info['evaluated'] + 1,
                              opportunity='equivalent_duplicate' if duplicate_opportunity else 'ordinary_random',
                              incumbent_makespan=best[0][0])
                if duplicate_opportunity:
                    record['replaced_equivalent_evaluation_id'] = known[canonical_key(trial)]
            structural_info['ledger'].append(record)
            known = {canonical_key(json.loads(key)) for key in cache}
            if canonical_key(component_plan) in known:
                record['status'] = 'equivalent_duplicate'
            elif structural_info.get('candidate_compute_bounds', {}).get(kind, structural_info['selected_compute_lower_bound']) > best[0][0]:
                record['status'] = 'compute_bound_exceeds_incumbent'
            else:
                entry = evaluate(component_plan, record['candidate'], observe_improving_only=True)
                record.update(proposal_ledger[-1])
                if entry:
                    structural_info['evaluated'] += 1
            if 'component_followup' in features and not followup_unlocked:
                # Strict primary-objective improvement, not merely fewer bytes.
                followup_unlocked = entry is not None and entry[0][0] < record['incumbent_makespan']
                structural_info['followup_unlocked'] = followup_unlocked
                record['unlocked_followup'] = followup_unlocked
                if not followup_unlocked:
                    structural_info['followup_skip_reason'] = 'first_probe_did_not_improve_makespan'
                    pending_component.clear()
        if entry is None:
            entry = evaluate(trial, label)
        if grain_record is not None:
            grain_record.update(proposal_ledger[-1])
        if entry:
            # Count-based reward keeps seeded runs reproducible across machine speeds.
            rewards[arm] += max(0., before - entry[0][0]) / max(1, baseline)
    if 'component_followup' in features and pending_component:
        structural_info['followup_skip_reason'] = 'no_unprotected_opportunity_before_budget_end'
    stats = {'method': 'experimental', 'features': sorted(features), 'seed': seed,
             'evaluator_backend': evaluator_backend,
             'official_calls_semantics': 'full global scoring calls, original or equivalent derived backend',
             'evaluation_budget': evaluation_budget, 'evaluations': history,
             'official_calls': sum(not r['cache_hit'] for r in history),
             'cache_hits': sum(r['cache_hit'] for r in history),
             'budget_unit': 'unique evaluated candidates including cache hits; hits do not buy extra search',
             'shared_input_stats': getattr(g, 'shared_input_stats', {}),
             'resource_init_stats': getattr(g, 'resource_init_stats', {}),
             'structural_seed_stats': structural_info,
             'protected_grain_attempts': protected_grain_attempts,
             'protected_grain_ledger': protected_grain_ledger,
             'proposal_ledger': proposal_ledger,
             'protected_prefix_evaluations': guarded_start if 'guarded_joint' in features else 0,
             'protected_prefix_makespan': protected_score,
             'budget_exhausted': len(history) == evaluation_budget,
             'singlecore_makespan': baseline, 'speedup': baseline / best[0][0] if best[0][0] else 1.,
             'rejected_proposals': rejected, 'local_cost_entries': len(g.local_observations),
             'local_cost_hits': g.cost_hits, 'local_cost_conflicts': g.observation_conflicts,
             'placement_stats': g.placement_stats,
             'guided_repair_stats': g.guided_repair_stats,
             'boundary_stats': g.boundary_stats,
             'chain_stats': g.chain_stats,
             'late_region_start': late_region_start,
             'region_stats': g.region_stats, 'region_attempts': region_attempts,
             'critical_refreshes': refreshes, 'arm_pulls': dict(pulls), 'arm_rewards': dict(rewards),
             'elite_scores': [e[0] for e in archive], 'elapsed_seconds': time.perf_counter() - started}
    return best[1], best[2], stats
