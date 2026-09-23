import unittest
from test_q1 import fixture, SETTINGS, WAITS, evaluate
from q1_experimental import CostGraph, solve_experimental
from q1_insertion import earliest_gap, schedule
from q1_solver import validate


class InsertionTests(unittest.TestCase):
    def test_gap_reserves_both_setup_waits(self):
        events = [(0, 10, 0), (100, 110, 1)]
        self.assertEqual(earliest_gap(events, 15, 20, 10), (20, 1))
        self.assertEqual(earliest_gap(events, 15, 80, 10), (120, 2))
        self.assertEqual(earliest_gap([(100, 110, 0)], 0, 90, 10), (0, 0))
        self.assertEqual(earliest_gap([(100, 110, 0)], 0, 91, 10), (120, 1))

    def test_disabled_matches_original_scheduler(self):
        g = CostGraph(fixture([(0, 2), (1, 2), (1, 3)]), SETTINGS, WAITS)
        mapping = {u: u for u in g.ops}
        self.assertEqual(schedule(g, mapping, 3, False, False), g.schedule(mapping, 3))

    def test_legal_and_reproducible_with_fixed_total_budget(self):
        raw = fixture([(u, u+10) for u in range(10)])
        for features in [['local_cost', 'critical', 'insertion'],
                         ['local_cost', 'critical', 'comm_rank'],
                         ['local_cost', 'critical', 'insertion', 'comm_rank']]:
            p, r, s = solve_experimental(raw, SETTINGS, WAITS, 4, 8, 7, features)
            p2, r2, s2 = solve_experimental(raw, SETTINGS, WAITS, 4, 8, 7, features)
            validate(CostGraph(raw, SETTINGS, WAITS), p)
            self.assertEqual(p, p2)
            self.assertEqual(r['makespan'], evaluate(raw, p)['makespan'])
            self.assertEqual(r['makespan'], r2['makespan'])
            self.assertEqual(len(s['evaluations']), 8)
            self.assertTrue(s['budget_exhausted'])


if __name__ == '__main__':
    unittest.main()
