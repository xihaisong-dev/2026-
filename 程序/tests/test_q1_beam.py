import unittest
from test_q1 import fixture, SETTINGS, WAITS, evaluate
from q1_solver import Graph, validate
from q1_beam import schedule
from q1_experimental import solve_experimental


class BeamTests(unittest.TestCase):
    def test_fork_join_legal_deterministic_and_proxy_kept(self):
        raw = fixture([(0, 2), (1, 2), (2, 3), (2, 4), (3, 5), (4, 5)])
        g = Graph(raw, SETTINGS, WAITS)
        mapping = {u: u for u in g.ops}
        for cores in (2, 3, 4, 5):
            plan, score, info = schedule(g, mapping, cores)
            validate(g, plan)
            self.assertEqual(plan['node_to_subgraph'], {str(u): u for u in mapping})
            self.assertEqual((plan, score, info), schedule(g, mapping, cores))
            self.assertLessEqual(score, info['baseline_proxy'])
            self.assertGreater(evaluate(raw, plan)['makespan'], 0)

    def test_size_cap_and_invalid_partition(self):
        g = Graph(fixture([(0, 1), (1, 2)]), SETTINGS, WAITS)
        _, _, info = schedule(g, {0: 0, 1: 1, 2: 2}, 2, max_tasks=2)
        self.assertTrue(info['fallback'])
        self.assertEqual(info['expanded'], 0)
        with self.assertRaises(ValueError):
            schedule(g, {0: 0, 1: 1, 2: 0}, 2)

    def test_official_budget_and_incumbent(self):
        raw = fixture([(u, u+10) for u in range(10)])
        features = ['local_cost', 'critical', 'insertion', 'comm_rank', 'beam']
        _, result, stats = solve_experimental(raw, SETTINGS, WAITS, 4, 12, 0, features)
        self.assertEqual(stats['official_calls'], 12)
        self.assertEqual(result['makespan'], min(x['makespan'] for x in stats['evaluations']))
        self.assertTrue(stats['placement_stats'])
