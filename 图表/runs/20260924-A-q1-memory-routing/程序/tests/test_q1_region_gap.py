import unittest
from test_q1 import fixture, SETTINGS, WAITS, evaluate
from q1_experimental import CostGraph, solve_experimental
from q1_region import rebuild, candidates
from q1_solver import validate


class RegionGapTests(unittest.TestCase):
    def test_fills_dependency_wait_gap(self):
        raw = fixture([(0, 1), (2, 3)])
        for op in raw['ops']:
            op['cycles'] = {0: 1000, 1: 10000, 2: 50, 3: 50}[op['id']]
        g = CostGraph(raw, SETTINGS, WAITS, True)
        mapping = {0: 0, 1: 1, 2: 2, 3: 2}
        old = {'node_to_subgraph': {str(u): s for u, s in mapping.items()},
               'core_schedules': [[0], [1, 2]]}
        append, _ = rebuild(g, old, mapping, {2}, 2)
        gap, _ = rebuild(g, old, mapping, {2}, 2, gap=True)
        self.assertEqual(gap['core_schedules'][1], [2, 1])
        self.assertNotEqual(append, gap)
        validate(g, gap)
        self.assertGreater(evaluate(raw, gap)['makespan'], 0)

    def test_budget_and_exterior(self):
        raw = fixture([(i, i+1) for i in range(11)])
        g = CostGraph(raw, SETTINGS, WAITS, True)
        plan = g.schedule({u: u for u in g.ops}, 3)[0]
        pool = list(candidates(g, plan, evaluate(raw, plan), 3, gap=True))
        region = set(g.region_stats[-1]['region'])
        self.assertLessEqual(g.region_stats[-1]['plan_proposals'], 12)
        self.assertTrue(pool)
        for _, trial in pool:
            validate(g, trial)
            for a, b in zip(plan['core_schedules'], trial['core_schedules']):
                exterior = set(plan['node_to_subgraph'].values()) - region
                self.assertEqual([s for s in a if s in exterior], [s for s in b if s in exterior])
        f = ['local_cost', 'critical', 'insertion', 'comm_rank', 'partition_guard',
             'shared_input', 'region', 'region_gap']
        _, result, stats = solve_experimental(raw, SETTINGS, WAITS, 3, 12, 0, f)
        self.assertEqual(stats['official_calls'], 12)
        self.assertEqual(stats['protected_grain_attempts'], [.5, 1., 2., .25])
        self.assertLessEqual(stats['region_attempts'], 1)
        self.assertEqual(result['makespan'], min(e['makespan'] for e in stats['evaluations']))
