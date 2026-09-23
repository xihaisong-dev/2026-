import gzip
import json
from pathlib import Path
import tempfile
import unittest
from collections import defaultdict
from test_q1 import fixture, SETTINGS, WAITS, evaluate
from q1_experimental import CostGraph, solve_experimental
from q1_search_tools import EvaluationCache, replay, diagnose, ranked_joint, choose_arm
from q1_solver import validate


class SearchToolsTests(unittest.TestCase):
    def test_fixed_replay_matches_wait_semantics(self):
        g = CostGraph(fixture([(0, 2), (1, 2)]), SETTINGS, WAITS)
        p = {'node_to_subgraph': {'0': 0, '1': 1, '2': 2}, 'core_schedules': [[0], [1], [2]]}
        self.assertEqual(replay(g, p, {0: 100, 1: 100, 2: 10}), 1110)
        self.assertEqual(replay(g, p, {0: 100, 1: 100, 2: 10}, False), 110)

    def test_diagnostic_residuals_sum_exactly(self):
        raw = fixture([(0, 1)])
        g = CostGraph(raw, SETTINGS, WAITS)
        p = g.schedule({0: 0, 1: 1}, 2)[0]
        result = evaluate(raw, p)
        d = diagnose(g, p, result, 100)
        self.assertEqual(d['local_model_residual']+d['global_replay_residual'], result['makespan']-100)

    def test_cache_invalidates_and_detects_corruption(self):
        with tempfile.TemporaryDirectory() as folder:
            raw = fixture([(0, 1)])
            c = EvaluationCache(folder, raw, SETTINGS, WAITS)
            plan = {'x': 1}
            self.assertFalse(c.run(plan, lambda: {'makespan': 3})[1])
            self.assertTrue(c.run(plan, lambda: self.fail('must reuse'))[1])
            changed = EvaluationCache(folder, raw, SETTINGS, dict(WAITS, task_cross_core_wait_cycles=999))
            self.assertFalse(changed.run(plan, lambda: {'makespan': 4})[1])
            self.assertFalse(c.run({'x': 2}, lambda: {'makespan': 5})[1])
            for p in Path(folder).glob('*.gz'):
                record = json.loads(gzip.decompress(p.read_bytes()))
                record['result']['makespan'] = 999
                p.write_bytes(gzip.compress(json.dumps(record).encode()))
            with self.assertRaisesRegex(ValueError, 'integrity'):
                c.run(plan, lambda: {})

    def test_joint_candidates_and_ddr_legality(self):
        raw = fixture([(u, u+10) for u in range(10)])
        g = CostGraph(raw, SETTINGS, WAITS, True)
        p = g.schedule({u: u//2 for u in g.ops}, 4)[0]
        r = evaluate(raw, p)
        g.observe(p, r)
        for ddr in [False, True]:
            proposals = list(ranked_joint(g, p, r, 4, ddr))
            self.assertGreater(len(proposals), 0)
            for _, trial in proposals:
                validate(g, trial)

    def test_cached_search_has_same_plan_without_extra_budget(self):
        features = ['local_cost', 'critical', 'insertion', 'comm_rank', 'calibrated', 'joint', 'budget_adapt', 'ddr']
        with tempfile.TemporaryDirectory() as folder:
            args = (fixture([(u, u+10) for u in range(10)]), SETTINGS, WAITS, 4, 12, 0, features)
            p, r, s = solve_experimental(*args, cache_dir=folder)
            p2, r2, s2 = solve_experimental(*args, cache_dir=folder)
            self.assertEqual(p, p2)
            self.assertEqual(r['makespan'], r2['makespan'])
            self.assertEqual(s['official_calls'], 12)
            self.assertEqual(s2['official_calls'], 0)
            self.assertEqual(s2['cache_hits'], 12)
            self.assertEqual(len(s2['evaluations']), 12)

    def test_budget_reserves_exploration(self):
        arms = ['split', 'migrate', 'reorder']
        pulls, rewards = defaultdict(int), defaultdict(float, split=10.)
        selected = []
        for i in range(20):
            arm = choose_arm(arms, pulls, rewards, i)
            selected.append(arm)
            pulls[arm] += 1
        self.assertEqual([selected[i] for i in [0, 4, 8]], arms)


if __name__ == '__main__':
    unittest.main()
