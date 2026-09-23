import unittest
from test_q1 import fixture, SETTINGS, WAITS, evaluate
from q1_solver import Graph
from q1_bounds import structural_bound


class BoundTests(unittest.TestCase):
    def test_parallel_work_bound(self):
        g = Graph(fixture([(u, u+10) for u in range(10)]), SETTINGS, WAITS)
        b = structural_bound(g, 4)
        self.assertEqual(b['lower_bound_cycles'], 50000)
        self.assertEqual(b['compute_critical_path_cycles'], 20000)
        self.assertFalse(b['attainability_proven'])

    def test_chain_bound_and_actual_feasible_schedule(self):
        raw = fixture([(u, u+1) for u in range(4)])
        g = Graph(raw, SETTINGS, WAITS)
        bound = structural_bound(g, 4)['lower_bound_cycles']
        self.assertEqual(bound, 50000)
        p = g.schedule({u: u for u in g.ops}, 4)[0]
        self.assertGreaterEqual(evaluate(raw, p)['makespan'], bound)
