"""Scene B: communication placement, lifetime ordering, bounded joint repair.

All proxies generate candidates only. The unmodified B evaluator accepts them.
No tensor splitting, operation duplication, or replacement of official spilling.
"""
from collections import defaultdict, Counter
import copy
import heapq
import random
import time
from q1_solver import Graph, greedy_partition, topological
from q2_evaluator import evaluate, key

VARIANTS = {'baseline': '', 'full': 'CLJ', 'no_C': 'LJ', 'no_L': 'CJ', 'no_J': 'CL'}
DEFAULTS = {'block_sizes': (16, 64, 256), 'ready_window': 32,
            'communication_weight': 1.0, 'lifetime_weight': 1.0,
            'joint_pool': 12, 'joint_region': 4, 'proposal_cap': 24}


class SceneBGraph(Graph):
    def __init__(self, raw, settings, delay):
        # These attributes only parameterize inherited partition construction.
        # They are NOT scene-A task wait constraints in evaluation.
        super().__init__(raw, settings, {'task_cross_core_wait_cycles': delay,
                                       'task_same_core_wait_cycles': 0})
        self.settings, self.delay = settings, delay
        # Official B also materializes direct operation edges as UB tensors.
        # Keep these separate: unlike ordinary tensor fanout they are per-edge.
        self.direct_edges = [(e['source'], e['target'], max(0, int(e.get('data_size', 0))))
                             for e in raw['edges']
                             if e['source'] in self.ops and e['target'] in self.ops]


def owner_of(plan):
    return {s: c for c, seq in enumerate(plan['core_schedules']) for s in seq}


def tensor_bytes(tensor, mapping, owner):
    """Base scheduled bytes for one tensor; partial owner maps allowed.

    Uses the official per producer-core/consumer-core COPY-pair convention.
    A tensor's final output copy is separate from its remote-consumer copies.
    """
    size, _, ps, cs, final = tensor
    pc = {owner[mapping[v]] for v in ps if mapping[v] in owner}
    cc = {owner[mapping[v]] for v in cs if mapping[v] in owner}
    incoming = len(cc) if not ps else 0
    outgoing = len(pc) if final or not cs else 0
    cross = sum(a != b for a in pc for b in cc)
    return size * (incoming + outgoing + 2 * cross)


def base_bytes(g, plan):
    mapping = {int(v): s for v, s in plan['node_to_subgraph'].items()}
    owner = owner_of(plan)
    return (sum(tensor_bytes(t, mapping, owner) for t in g.tensors)
            + sum(2 * size for u,v,size in g.direct_edges
                  if owner[mapping[u]] != owner[mapping[v]]))


def context(g, mapping):
    groups, pred, succ, order = g.view(mapping)
    incident, loads = {}, {}
    for s, nodes in groups.items():
        incident[s] = sorted({i for v in nodes for i in g.incident[v]})
        load = defaultdict(int)
        for v in sorted(nodes):
            load[g.ops[v]['pipe']] += g.ops[v]['cycles']
        loads[s] = dict(load)
    ranks = {}
    for s in reversed(order):
        ranks[s] = max(loads[s].values(), default=0) + max((ranks[v] for v in succ[s]), default=0)
    return groups, pred, succ, order, incident, loads, ranks


def place(g, mapping, cores, communication=True, weight=1.0):
    """Topological list placement using Pipe load and de-duplicated marginal bytes."""
    groups, pred, succ, _, incident, loads, ranks = context(g, mapping)
    order = topological(pred, succ, ranks)
    direct = defaultdict(list)
    for u,v,size in g.direct_edges:
        for sg in {mapping[u],mapping[v]}: direct[sg].append((u,v,size))
    def edge_bytes(s, assigned):
        return sum(2*size for u,v,size in direct[s]
                   if mapping[u] in assigned and mapping[v] in assigned
                   and assigned[mapping[u]] != assigned[mapping[v]])
    owners, end = {}, {}
    core_load = [defaultdict(float) for _ in range(cores)]
    for s in order:
        before = sum(tensor_bytes(g.tensors[i], mapping, owners) for i in incident[s]) + edge_bytes(s,owners)
        options = []
        for c in range(cores):
            trial = dict(owners); trial[s] = c
            delta = sum(tensor_bytes(g.tensors[i], mapping, trial) for i in incident[s]) + edge_bytes(s,trial) - before
            work = max((core_load[c][p] + loads[s].get(p, 0)
                        for p in set(core_load[c]) | set(loads[s])), default=0)
            release = max((end[p] + (g.delay if owners[p] != c else 0)
                           for p in pred[s]), default=0)
            finish = max(work, release + max(loads[s].values(), default=0))
            score = finish + (weight * delta / g.bandwidth if communication else 0)
            options.append((score, finish, c))
        _, finish, c = min(options)
        owners[s], end[s] = c, finish
        for p, amount in loads[s].items():
            core_load[c][p] += amount
    return owners


def order_plan(g, mapping, owners, cores, lifetime=True, window=32, weight=1.0,
               random_priority=None):
    """Project ONE global legal group order to cores; no core-graph contraction.

    Lifetime is a group-level no-spill proxy. External COPY_OUT timing and Pipe
    overlap are resolved only by the official evaluator.
    """
    groups, pred, succ, _, incident, loads, ranks = context(g, mapping)
    counts = Counter()
    for s in groups:
        for i in incident[s]:
            counts[owners[s], i] += 1
    live = [set() for _ in range(cores)]
    resident = [defaultdict(int) for _ in range(cores)]
    degree = {s: len(pred[s]) for s in groups}
    priority = random_priority or ranks
    ready = [(-priority[s], s) for s in groups if degree[s] == 0]
    heapq.heapify(ready)
    schedules = [[] for _ in range(cores)]
    rank_scale = max(ranks.values(), default=1) or 1
    while ready:
        candidates = [heapq.heappop(ready) for _ in range(min(window if lifetime else 1, len(ready)))]
        def score(item):
            _, s = item; c = owners[s]
            added, freed = defaultdict(int), defaultdict(int)
            for i in incident[s]:
                size, tier, *_ = g.tensors[i]
                if i not in live[c]: added[tier] += size
                if counts[c, i] == 1: freed[tier] += size
            pressure = sum(max(0, resident[c][r] + added[r] - cap) / cap
                           for r, cap in g.capacity.items())
            delta = sum((added[r] - freed[r]) / cap for r, cap in g.capacity.items())
            return (weight * (pressure + delta) - ranks[s] / rank_scale, -ranks[s], s)
        chosen = min(candidates, key=score) if lifetime else candidates[0]
        for item in candidates:
            if item != chosen: heapq.heappush(ready, item)
        s = chosen[1]; c = owners[s]; schedules[c].append(s)
        for i in incident[s]:
            size, tier, *_ = g.tensors[i]
            if i not in live[c]: live[c].add(i); resident[c][tier] += size
            counts[c, i] -= 1
            if counts[c, i] == 0: live[c].remove(i); resident[c][tier] -= size
        for v in sorted(succ[s]):
            degree[v] -= 1
            if degree[v] == 0: heapq.heappush(ready, (-priority[v], v))
    if sum(map(len, schedules)) != len(groups): raise ValueError('Cyclic group order')
    return {'node_to_subgraph': {str(v): mapping[v] for v in sorted(mapping)},
            'core_schedules': schedules}


def proxy(g, plan):
    """Cycles-scaled ranking only; neither exact time nor a feasibility proof."""
    mapping = {int(v): s for v, s in plan['node_to_subgraph'].items()}
    owners = owner_of(plan)
    loads = [defaultdict(int) for _ in plan['core_schedules']]
    positions = {}
    groups = defaultdict(list)
    for v in g.order: groups[mapping[v]].append(v)
    for c, seq in enumerate(plan['core_schedules']):
        n = 0
        for s in seq:
            for v in groups[s]:
                positions[v] = n; n += 1
                loads[c][g.ops[v]['pipe']] += g.ops[v]['cycles']
    events = [defaultdict(lambda: defaultdict(int)) for _ in loads]
    for size, tier, ps, cs, _ in g.tensors:
        uses = defaultdict(list)
        for v in sorted(ps | cs): uses[owners[mapping[v]]].append(positions[v])
        for c, pos in uses.items():
            events[c][min(pos)][tier] += size
            events[c][max(pos) + 1][tier] -= size
    excess = 0
    for changes in events:
        live, peak = defaultdict(int), defaultdict(int)
        for j in sorted(changes):
            for tier, d in changes[j].items():
                live[tier] += d; peak[tier] = max(peak[tier], live[tier])
        excess += sum(max(0, peak[r] - cap) for r, cap in g.capacity.items())
    traffic = base_bytes(g, plan)
    work = max((max(d.values(), default=0) for d in loads), default=0)
    return max(work, traffic / g.bandwidth) + 2 * excess / g.bandwidth


def proposal(g, plan, cores, rng, features, cfg, joint=False):
    mapping = {int(v): s for v, s in plan['node_to_subgraph'].items()}
    owners = owner_of(plan)
    groups, pred, succ, order, incident, loads, ranks = context(g, mapping)
    if not groups: return copy.deepcopy(plan), {'move': 'empty'}
    if joint:
        # Inspect at most a bounded set of high criticality / communication groups.
        ranked = sorted(groups, key=lambda s: (-(ranks[s] + sum(g.tensors[i][0] for i in incident[s]) / g.bandwidth), s))
        offset = rng.randrange(max(1, len(ranked)))
        region = list(dict.fromkeys(ranked[:max(1, cfg['joint_region']//2)] + ranked[offset:offset+cfg['joint_region']]))[:cfg['joint_region']]
        choices = [(s,c) for s in region for c in range(cores) if owners[s] != c]
        rng.shuffle(choices)
        candidates = []
        for s,c in choices[:cfg['joint_pool']]:
            target = dict(owners); target[s] = c
            trial = order_plan(g,mapping,target,cores,'L' in features,cfg['ready_window'],cfg['lifetime_weight'])
            candidates.append((proxy(g,trial),key(trial),trial,{'move':'joint_migrate_order','subgraph':s,'core':c}))
        if candidates:
            _,_,trial,info = min(candidates, key=lambda x:x[:2]); return trial,info
    kind = rng.choice(('migrate','order','split','boundary'))
    if kind == 'migrate':
        s = rng.choice(sorted(groups)); owners[s] = rng.randrange(cores)
    elif kind == 'split':
        choices = [s for s in sorted(groups) if len(groups[s]) > 1]
        if choices:
            s = rng.choice(choices); nodes = sorted(groups[s],key=g.pos.get)
            cut = len(nodes)//2; new = max(groups)+1
            for v in nodes[cut:]: mapping[v] = new
            owners[new] = owners[s]
    elif kind == 'boundary':
        edges = [(u,v) for u in g.order for v in sorted(g.succ[u]) if mapping[u]!=mapping[v]]
        if edges:
            u,v = rng.choice(edges); mapping[u] = mapping[v]
            valid_groups = set(mapping.values()); owners = {s:c for s,c in owners.items() if s in valid_groups}
    # Splits or boundary moves must recheck quotient acyclicity before ranking.
    _,p,s,_,_,_,r = context(g,mapping)
    random_priority = {v:rng.random() for v in p} if kind=='order' else None
    trial = order_plan(g,mapping,owners,cores,'L' in features and kind!='order',
                       cfg['ready_window'],cfg['lifetime_weight'],random_priority)
    return trial,{'move':kind}


def solve(raw, settings, delay, cores, budget=12, seed=0, variant='full', params=None,
          on_evaluation=None):
    if cores not in range(1,6) or budget < 1: raise ValueError('Invalid cores/budget')
    features = VARIANTS[variant]
    cfg = {**DEFAULTS, **(params or {})}
    if set(cfg) != set(DEFAULTS): raise ValueError('Unknown parameter')
    if any(cfg[k] < 1 for k in ('ready_window','joint_pool','joint_region','proposal_cap')):
        raise ValueError('Window/pool/region/proposal limits must be positive')
    if not cfg['block_sizes'] or any(x < 1 for x in cfg['block_sizes']):
        raise ValueError('Block sizes must be positive')
    if any(cfg[k] < 0 for k in ('communication_weight','lifetime_weight')):
        raise ValueError('Weights must be nonnegative')
    rng = random.Random(seed)
    g = SceneBGraph(raw,settings,delay)
    rows, generation_errors = [], []
    best_plan = best_result = None
    seen = set()
    # Cache only compact failures; full success outputs are not accumulated in RAM.
    def assess(plan,label,info=None):
        nonlocal best_plan,best_result
        started=time.perf_counter(); fingerprint=key(plan)
        row={'candidate':label,'plan_sha256':fingerprint,'duplicate':fingerprint in seen,
             'mechanism':info or {}}
        seen.add(fingerprint)
        try:
            result=evaluate(raw,plan,settings,delay)
            objective=(result['makespan'],result['data_movement_bytes']['added_copy_bytes'])
            row.update(status='success',makespan=objective[0],added_copy_bytes=objective[1],
                       partition_added_copy_bytes=result['data_movement_bytes']['partition_added_copy_bytes'],
                       spill_added_copy_bytes=result['data_movement_bytes']['spill_added_copy_bytes'])
            if best_result is None or objective < (best_result['makespan'],best_result['data_movement_bytes']['added_copy_bytes']):
                best_plan,best_result=copy.deepcopy(plan),result;row['accepted']=True
            else: row['accepted']=False
        except (ValueError, RuntimeError) as exc:
            row.update(status='error',error_type=type(exc).__name__,error=str(exc))
        row['seconds']=time.perf_counter()-started;rows.append(row)
        if on_evaluation: on_evaluation(row)
    whole={'node_to_subgraph':{str(v):0 for v in sorted(g.ops)},'core_schedules':[[0] if g.ops else []]+[[] for _ in range(cores-1)]}
    assess(whole,'whole_graph')
    if cores>1:
        for size in cfg['block_sizes']:
            if len(rows)>=budget: break
            mapping=greedy_partition(g,cores,size)
            owners=place(g,mapping,cores,'C' in features,cfg['communication_weight'])
            plan=order_plan(g,mapping,owners,cores,'L' in features,cfg['ready_window'],cfg['lifetime_weight'])
            assess(plan,'initial_'+str(size))
        while len(rows)<budget:
            if best_plan is None: break
            trial=None; info={}
            for attempt in range(cfg['proposal_cap']):
                try:
                    trial,info=proposal(g,best_plan,cores,rng,features,cfg,joint=('J' in features and len(rows)%2==0))
                    if key(trial) not in seen: break
                except ValueError as exc:
                    generation_errors.append({'evaluation_slot':len(rows),'attempt':attempt,'error':str(exc)})
                    trial=None
            if trial is None: trial=copy.deepcopy(best_plan);info={'move':'bounded_fallback'}
            assess(trial,'repair_'+str(len(rows)),info)
    if best_result is None: raise RuntimeError('No scene-B feasible candidate; evaluation errors: '+str(rows))
    return best_plan,best_result,{'variant':variant,'features':list(features),'seed':seed,'budget':budget,
                                 'parameters':cfg,'evaluations':rows,'evaluation_count':len(rows),
                                 'official_calls':len(rows),'generation_errors':generation_errors}
