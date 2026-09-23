import unittest
from test_q1 import fixture, SETTINGS, WAITS, evaluate
from q1_experimental import CostGraph, solve_experimental
from q1_region import candidates, rebuild
from q1_solver import validate


class RegionTests(unittest.TestCase):
    def test_bounds_legality_and_exterior(self):
        raw = fixture([(i, i+1) for i in range(11)])
        g = CostGraph(raw, SETTINGS, WAITS, True)
        mapping = {u: u for u in g.ops}
        plan = g.schedule(mapping, 3)[0]
        result = evaluate(raw, plan)
        proposals = list(candidates(g, plan, result, 3))
        info = g.region_stats[-1]
        self.assertTrue(proposals)
        self.assertLessEqual(len(info['region']), 4)
        self.assertLessEqual(info['nodes'], 512)
        self.assertLessEqual(info['mapping_proposals'], 6)
        self.assertLessEqual(info['plan_proposals'], 12)
        self.assertLessEqual(len(proposals), 2)
        region = set(info['region'])
        for _, trial in proposals:
            validate(g, trial)
            for u, s in mapping.items():
                if s not in region:
                    self.assertEqual(trial['node_to_subgraph'][str(u)], s)
            for a, b in zip(plan['core_schedules'], trial['core_schedules']):
                self.assertEqual([s for s in a if s not in region],
                                 [s for s in b if s in mapping.values() and s not in region])
            self.assertGreater(evaluate(raw, trial)['makespan'], 0)
        self.assertEqual(proposals, list(candidates(g, plan, result, 3)))

    def test_budget_and_best_official(self):
        raw = fixture([(i, i+10) for i in range(10)])
        features = ['local_cost', 'critical', 'insertion', 'comm_rank',
                    'partition_guard', 'shared_input', 'region']
        _, result, stats = solve_experimental(raw, SETTINGS, WAITS, 4, 12, 0, features)
        self.assertEqual(stats['official_calls'], 12)
        self.assertEqual(stats['protected_grain_attempts'], [.5, 1., 2., .25])
        self.assertLessEqual(stats['region_attempts'], 1)
        labels = [e['candidate'] for e in stats['evaluations']]
        self.assertLessEqual(sum(x.startswith('region_') for x in labels), 1)
        self.assertTrue(stats['region_stats'])
        _, _, base = solve_experimental(raw, SETTINGS, WAITS, 4, 12, 0, features[:-1])
        first = next(i for i, e in enumerate(stats['evaluations']) if e['candidate'].startswith('region_'))
        fields = lambda es: [(e['candidate'], e['makespan']) for e in es]
        self.assertEqual(fields(stats['evaluations'][:first]), fields(base['evaluations'][:first]))
        self.assertEqual(result['makespan'], min(e['makespan'] for e in stats['evaluations']))

    def test_reject_cyclic_contraction(self):
        g = CostGraph(fixture([(0, 1), (1, 2)]), SETTINGS, WAITS)
        plan = g.schedule({0: 0, 1: 1, 2: 2}, 2)[0]
        with self.assertRaises(ValueError):
            rebuild(g, plan, {0: 0, 1: 1, 2: 0}, {0, 2}, 2)
