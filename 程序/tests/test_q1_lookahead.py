import unittest
from test_q1 import fixture, SETTINGS, WAITS, evaluate
from q1_experimental import CostGraph, solve_experimental
from q1_solver import validate
from q1_lookahead import candidates


class LookaheadTests(unittest.TestCase):
    def test_bounded_candidates_preserve_coverage_and_legality(self):
        raw = fixture([(u, u+1) for u in range(15)])
        g = CostGraph(raw, SETTINGS, WAITS, True)
        p = g.schedule({u: u//4 for u in g.ops}, 4)[0]
        result = evaluate(raw, p)
        g.observe(p, result)
        proposals = list(candidates(g, p, result, 4))
        self.assertGreater(len(proposals), 0)
        self.assertLessEqual(len(proposals), 12)
        for _, trial in proposals:
            validate(g, trial)
            self.assertEqual(set(trial['node_to_subgraph']), set(p['node_to_subgraph']))

    def test_fixed_budget_and_determinism(self):
        raw = fixture([(u, u+10) for u in range(10)])
        features = ['local_cost', 'critical', 'insertion', 'comm_rank', 'lookahead']
        p, r, s = solve_experimental(raw, SETTINGS, WAITS, 4, 12, 0, features)
        p2, r2, _ = solve_experimental(raw, SETTINGS, WAITS, 4, 12, 0, features)
        self.assertEqual(p, p2)
        self.assertEqual(r['makespan'], r2['makespan'])
        self.assertEqual(len(s['evaluations']), 12)
        self.assertLessEqual(r['makespan'], s['singlecore_makespan'])
