import unittest
from test_q1 import fixture, SETTINGS, WAITS, evaluate
from q1_experimental import CostGraph, solve_experimental
from q1_guided_repair import guided_repair
from q1_solver import validate


class GuidedRepairTests(unittest.TestCase):
    def test_bounded_deterministic_legal_proxy_not_worse(self):
        raw = fixture([(0, 2), (1, 3), (4, 5)])
        g = CostGraph(raw, SETTINGS, WAITS, True)
        g.insertion = g.communication_rank = True
        plan = {'node_to_subgraph': {'0': 0, '1': 0, '2': 0, '3': 0, '4': 1, '5': 1},
                'core_schedules': [[0], [1], []]}
        mapping = {0: 0, 1: 2, 2: 0, 3: 2, 4: 1, 5: 1}
        trial = guided_repair(g, plan, mapping, 3)
        validate(g, trial)
        self.assertEqual(trial['node_to_subgraph'], {str(u): s for u, s in mapping.items()})
        info = g.guided_repair_stats[-1]
        self.assertLessEqual(info['proposed'], 6)
        self.assertLessEqual(info['selected_proxy'], info['global_proxy'])
        self.assertEqual(trial, guided_repair(g, plan, mapping, 3))
        self.assertGreater(evaluate(raw, trial)['makespan'], 0)

    def test_budget_protection_and_incumbent(self):
        raw = fixture([(u, u+10) for u in range(10)])
        features = ['local_cost', 'critical', 'insertion', 'comm_rank',
                    'partition_guard', 'shared_input', 'repair_move']
        _, result, stats = solve_experimental(raw, SETTINGS, WAITS, 4, 12, 0, features)
        self.assertEqual(stats['official_calls'], 12)
        self.assertEqual(stats['protected_grain_attempts'], [.5, 1., 2., .25])
        self.assertEqual(result['makespan'], min(r['makespan'] for r in stats['evaluations']))
        self.assertTrue(stats['guided_repair_stats'])
        self.assertTrue(all(r['proposed'] <= 6 for r in stats['guided_repair_stats']))
