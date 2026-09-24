"""Exact global replay with instance-local, bounded partition preparation reuse.

Does not modify the official module. Every candidate still executes the complete
official global event loop, including dynamic DDR sharing and release waits.
"""
from collections import OrderedDict
import copy
import json
import types


class PartitionEvaluator:
    def __init__(self, raw, bandwidth, capacity, cross, same, max_partitions=2, backend_engine=None):
        from q1_io import official
        self.module = official()
        self.raw = copy.deepcopy(raw)
        self.bandwidth, self.capacity = bandwidth, dict(capacity)
        self.cross, self.same = cross, same
        if max_partitions < 1:
            raise ValueError('max_partitions must be positive')
        self.limit = max_partitions
        self.cache = OrderedDict()
        self.hits = self.misses = self.evaluations = 0
        original = backend_engine or self.module.evaluate_scene_a
        self.task_builder = original.__globals__['_build_scene_a_tasks']
        namespace = dict(original.__globals__)
        namespace['_build_scene_a_tasks'] = self._build
        self.engine = types.FunctionType(original.__code__, namespace,
                                         original.__name__, original.__defaults__,
                                         original.__closure__)

    def _build(self, raw, plan, bandwidth, capacity):
        # Context fixed for the lifetime of this object; no persistent cache.
        # Full mapping INCLUDING task IDs preserves generated boundary IDs.
        view = self.module.derive_multicore_plan(raw, plan)
        self.module.validate_task_order(view)  # Never bypass legality on a hit.
        key = tuple(sorted(view['mapping'].items()))
        if key not in self.cache:
            built = self.task_builder(raw, plan, bandwidth, capacity)
            self.cache[key] = copy.deepcopy(built[:3])
            self.misses += 1
            if len(self.cache) > self.limit:
                self.cache.popitem(last=False)
        else:
            self.hits += 1
            self.cache.move_to_end(key)
        tasks, traffic, movement = copy.deepcopy(self.cache[key])
        for task_id, task in tasks.items():
            task['core_id'] = view['core_by_subgraph'][task_id]
            task['pred_tasks'] = view['subgraph_preds'][task_id]
        return tasks, traffic, movement, view

    def evaluate(self, plan):
        result = self.engine(self.raw, plan, self.bandwidth, self.capacity,
                             self.cross, self.same)
        self.evaluations += 1
        return result


def candidates(g, plan, result, limit=8):
    """Fixed-partition candidates; frozen exact local durations only rank proposals."""
    from q1_insertion import schedule
    from q1_search_tools import replay
    from q1_solver import validate
    mapping = {int(u): s for u, s in plan['node_to_subgraph'].items()}
    cores = len(plan['core_schedules'])
    local = {int(s): t['local_makespan'] for s, t in result['step3_by_task'].items()}
    pool, seen = [], {json.dumps(plan, sort_keys=True)}

    def add(label, trial):
        key = json.dumps(trial, sort_keys=True)
        if key in seen:
            return
        seen.add(key)
        try:
            validate(g, trial)
            score = replay(g, trial, local)
        except (ValueError, RuntimeError):
            return
        pool.append((score, key, label, trial))

    add('reschedule', schedule(g, mapping, cores, True, True)[0])
    tasks = [t for c in result['per_core_timeline'] for t in c['tasks']]
    tasks.sort(key=lambda t: (-t['end'], -t['duration'], t['task_id']))
    for task in tasks[:4]:
        s = task['task_id']
        source = next(c for c, seq in enumerate(plan['core_schedules']) if s in seq)
        for target, seq in enumerate(plan['core_schedules']):
            # Bound construction; test head/tail and the neighborhood of midpoint.
            for position in sorted({0, len(seq)//2, len(seq)}):
                trial = copy.deepcopy(plan)
                trial['core_schedules'][source].remove(s)
                at = min(position, len(trial['core_schedules'][target]))
                trial['core_schedules'][target].insert(at, s)
                add('tail_move', trial)
        seq = plan['core_schedules'][source]
        i = seq.index(s)
        for j in (i-1, i+1):
            if 0 <= j < len(seq):
                trial = copy.deepcopy(plan)
                trial['core_schedules'][source][i], trial['core_schedules'][source][j] = seq[j], seq[i]
                add('adjacent_swap', trial)
    pool.sort(key=lambda x: x[:2])
    return [(label, trial, score) for score, _, label, trial in pool[:limit]]
