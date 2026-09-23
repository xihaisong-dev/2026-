import unittest
from unittest.mock import patch
from test_q1 import fixture, SETTINGS, WAITS, evaluate
from q1_fast_evaluator import evaluate_scene_a, evaluator
from q1_experimental import solve_experimental
from q1_submit import BASELINE_FEATURES


class CompletionCounterTests(unittest.TestCase):
    def test_cached_base_costs_match_including_membership_changes(self):
        from q1_solver import Graph, greedy_partition, multilevel
        from q1_fast_costs import costs
        raw = fixture([(i, i+8) for i in range(8)])
        g = Graph(raw, SETTINGS, WAITS)
        for width in [1, 2, 4, 8, 16, 2, 1]:
            mapping = {u: i // width for i, u in enumerate(g.order)}
            self.assertEqual(g.costs(mapping), costs(g, mapping))
            renamed = {u: 100-s for u, s in reversed(list(mapping.items()))}
            self.assertEqual(g.costs(renamed), costs(g, renamed))

    def test_full_results_and_search_trajectory(self):
        for edges in [[(0, 1), (0, 2), (1, 3), (2, 3)], [(i, i+8) for i in range(8)]]:
            raw = fixture(edges)
            for n in [1, 2, 5]:
                a, b, c = solve_experimental(raw, SETTINGS, WAITS, n, 12, 0, BASELINE_FEATURES)
                d, e, f = solve_experimental(raw, SETTINGS, WAITS, n, 12, 0, BASELINE_FEATURES,
                                            evaluator_backend='counter')
                self.assertEqual((a, b), (d, e))
                self.assertEqual([(x['candidate'], x['makespan'], x['added_copy_bytes']) for x in c['evaluations']],
                                 [(x['candidate'], x['makespan'], x['added_copy_bytes']) for x in f['evaluations']])
                self.assertEqual(c['official_calls'], f['official_calls'])
                self.assertEqual(c['proposal_ledger'], f['proposal_ledger'])

    def test_hash_guard(self):
        evaluator.cache_clear()
        with patch('q1_fast_evaluator.OFFICIAL_SHA256', 'changed'):
            with self.assertRaises(ValueError):
                evaluator()
        evaluator.cache_clear()


if __name__ == '__main__':
    unittest.main()
