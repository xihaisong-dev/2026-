"""Pre-evaluation local preparation: official Pipe/spill cost, approximate global replay.

No candidate global outcome is read. Cache includes the full partition because
boundary IDs and official heuristic tie breaking can depend on other Tasks.
"""
import time
import json
import copy
from collections import OrderedDict
from q1_exact_placement import PartitionEvaluator
from q1_search_tools import replay


class LocalRank:
    def __init__(self, raw, g, phase=False, event=False, preparer=None, reuse_scores=False):
        self.g = g
        self.phase = phase
        self.event = event
        self.event_seconds = 0.
        self.event_stats = []
        self.preparer = preparer or PartitionEvaluator(raw, g.bandwidth, g.capacity, g.cross, g.same)
        self.reuse_scores = reuse_scores
        self.score_cache = OrderedDict()
        self.score_hits = 0
        self.seconds = 0.
        self.calls = 0
        self.phase_seconds = 0.
        self.last_components = {}

    def score(self, plan):
        start = time.perf_counter()
        key = json.dumps(plan, sort_keys=True)
        if self.reuse_scores and key in self.score_cache:
            self.score_hits += 1
            self.score_cache.move_to_end(key)
            value, duration, traffic, self.last_components = copy.deepcopy(self.score_cache[key])
            return value, duration, traffic
        tasks, _, traffic, _ = self.preparer._build(
            self.preparer.raw, plan, self.g.bandwidth, self.g.capacity)
        duration = {s: t['step3']['makespan'] for s,t in tasks.items()}
        value = replay(self.g, plan, duration)
        if self.event:
            from q1_pipe_event import event_time
            event_start = time.perf_counter()
            event_value, info = event_time(self.g,plan,tasks)
            self.event_seconds += time.perf_counter()-event_start
            self.event_stats.append(info)
            self.last_components = {'local': value, 'event': event_value}
            value = event_value
        elif self.phase:
            from q1_ddr_phase import profile, phase_time
            phase_start = time.perf_counter()
            phase_value = phase_time(self.g, plan, {s:profile(t) for s,t in tasks.items()})
            self.phase_seconds += time.perf_counter()-phase_start
            self.last_components = {'local': value, 'phase': phase_value}
            value = phase_value
        if self.reuse_scores:
            self.score_cache[key] = copy.deepcopy((value, duration, traffic, self.last_components))
            if len(self.score_cache)>8:
                self.score_cache.popitem(last=False)
        self.seconds += time.perf_counter()-start
        self.calls += 1
        return value, duration, traffic

    def stats(self):
        return {'seconds': self.seconds, 'calls': self.calls, 'score_cache_hits': self.score_hits,
                'partition_hits': self.preparer.hits,
                'partition_misses': self.preparer.misses,
                'uncached_global_builds': self.preparer.uncached_builds,
                'global_evaluations': self.preparer.evaluations,
                'global_evaluations_semantics': 'lifetime paid calls on preparer; ranking/gate deltas audited separately',
                'phase_seconds': self.phase_seconds, 'event_seconds': self.event_seconds,
                'event_passes': 3 if self.event else 0,
                'event_max_nodes': max((x['nodes'] for x in self.event_stats),default=0)}
