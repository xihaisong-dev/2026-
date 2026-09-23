import unittest
from test_q1 import fixture, SETTINGS, WAITS, evaluate
from q1_experimental import CostGraph, solve_experimental
from q1_frozen_cost import FrozenCost, fluid_time
from q1_boundary_refine import pool
from q1_solver import validate


class FrozenTests(unittest.TestCase):
    def test_fluid_shared_bandwidth_and_serial_limit(self):
        g = CostGraph(fixture([(0, 1)]), SETTINGS, WAITS)
        # Use independent tasks for the analytic bandwidth test.
        g.pred = {0: set(), 1: set()}; g.succ = {0: set(), 1: set()}
        plan = {'node_to_subgraph': {'0': 0, '1': 1}, 'core_schedules': [[0], [1]]}
        self.assertAlmostEqual(fluid_time(g, plan, {0: 10, 1: 10}, {0: 10, 1: 10}), 20)
        self.assertAlmostEqual(fluid_time(g, plan, {0: 10, 1: 10}, {0: 0, 1: 0}), 10)
        plan['core_schedules'] = [[0, 1]]
        self.assertAlmostEqual(fluid_time(g, plan, {0: 10, 1: 10}, {0: 10, 1: 10}), 120)

    def test_frozen_snapshot_does_not_follow_new_observations(self):
        raw = fixture([(0, 1), (2, 3)])
        g = CostGraph(raw, SETTINGS, WAITS, True)
        plan = g.schedule({u: u for u in g.ops}, 2)[0]
        result = evaluate(raw, plan); g.observe(plan, result)
        frozen = FrozenCost(g, plan, result)
        first = frozen.score(plan)
        g.local_observations[(0,)] = 999999
        frozen.cache.clear()
        self.assertEqual(first, frozen.score(plan)); frozen.check()
        frozen.g.local_observations[(0,)] = 12345
        with self.assertRaises(RuntimeError): frozen.check()

    def test_bounded_acyclic_refinement_and_budget(self):
        raw = fixture([(i, i+10) for i in range(10)])
        g = CostGraph(raw, SETTINGS, WAITS, True)
        plan = g.schedule({u: u//2 for u in g.ops}, 4)[0]
        result = evaluate(raw, plan); g.observe(plan, result)
        ranked, frozen = pool(g, plan, result, 4, True, True)
        info = g.boundary_stats[-1]
        self.assertLessEqual(info['boundary_probes'], 12)
        self.assertLessEqual(info['accepted_steps'], 3)
        self.assertLessEqual(len(ranked), 15)
        self.assertTrue(all(a > b for a,b in zip(info['accepted_scores'], info['accepted_scores'][1:])))
        region = set(g.region_stats[-1]['region'])
        exterior = set(plan['node_to_subgraph'].values()) - region
        for _, _, trial in ranked:
            validate(g, trial)
            for u, group in plan['node_to_subgraph'].items():
                if group in exterior:
                    self.assertEqual(trial['node_to_subgraph'][u], group)
            for before, after in zip(plan['core_schedules'], trial['core_schedules']):
                self.assertEqual([s for s in before if s in exterior], [s for s in after if s in exterior])
        frozen.check()
        features = ['local_cost','critical','insertion','comm_rank','partition_guard','shared_input','region','fluid_rank','boundary_refine']
        _, result, stats = solve_experimental(raw, SETTINGS, WAITS, 4, 12, 0, features)
        self.assertEqual(stats['official_calls'], 12)
        self.assertEqual(stats['protected_grain_attempts'], [.5,1.,2.,.25])
        self.assertEqual(result['makespan'], min(e['makespan'] for e in stats['evaluations']))
        self.assertLessEqual(stats['region_attempts'], 1)
