"""Pre-evaluation local preparation: official Pipe/spill cost, approximate global replay.

No candidate global outcome is read. Cache includes the full partition because
boundary IDs and official heuristic tie breaking can depend on other Tasks.
"""
import time
from q1_exact_placement import PartitionEvaluator
from q1_search_tools import replay


class LocalRank:
    def __init__(self, raw, g):
        self.g = g
        self.preparer = PartitionEvaluator(raw, g.bandwidth, g.capacity, g.cross, g.same)
        self.seconds = 0.
        self.calls = 0

    def score(self, plan):
        start = time.perf_counter()
        tasks, _, traffic, _ = self.preparer._build(
            self.preparer.raw, plan, self.g.bandwidth, self.g.capacity)
        duration = {s: t['step3']['makespan'] for s,t in tasks.items()}
        value = replay(self.g, plan, duration)
        self.seconds += time.perf_counter()-start
        self.calls += 1
        return value, duration, traffic

    def stats(self):
        return {'seconds': self.seconds, 'calls': self.calls,
                'partition_hits': self.preparer.hits,
                'partition_misses': self.preparer.misses,
                'global_evaluations': self.preparer.evaluations}
