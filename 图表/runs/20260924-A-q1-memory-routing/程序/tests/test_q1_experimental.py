import unittest
from test_q1 import fixture, SETTINGS, WAITS, evaluate
from q1_experimental import CostGraph, task_slacks, adaptive_partition, solve_experimental, FEATURES
from q1_solver import validate


class ExperimentalTests(unittest.TestCase):
    def test_observed_local_duration_is_not_global_duration(self):
        raw = fixture([(0, 1), (0, 2)])
        g = CostGraph(raw, SETTINGS, WAITS, True)
        plan = {'node_to_subgraph': {'0': 0, '1': 1, '2': 2}, 'core_schedules': [[0, 1], [2]]}
        result = evaluate(raw, plan)
        g.observe(plan, result)
        costs, _, _ = g.costs({0: 0, 1: 1, 2: 2})
        self.assertEqual(costs, {s: v['local_makespan'] for s, v in result['step3_by_task'].items()})
        self.assertGreater(g.cost_hits, 0)

    def test_slack_uses_dependencies_and_core_waits(self):
        raw = fixture([(1, 2)])
        raw['ops'].append({'id': 0, 'op': 'CUSTOM', 'pipe': 'PIPE_V', 'cycles': 80})
        g = CostGraph(raw, SETTINGS, WAITS)
        plan = {'node_to_subgraph': {'0': 0, '1': 1, '2': 2}, 'core_schedules': [[0], [1, 2]]}
        result = {'makespan': 200, 'per_core_timeline': [
            {'tasks': [{'task_id': 0, 'start': 0, 'end': 80, 'duration': 80}]},
            {'tasks': [{'task_id': 1, 'start': 0, 'end': 50, 'duration': 50},
                       {'task_id': 2, 'start': 150, 'end': 200, 'duration': 50}]}]}
        self.assertEqual(task_slacks(g, plan, result), {0: 120, 1: 0, 2: 0})

    def test_adaptive_partition_covers_original_ops(self):
        g = CostGraph(fixture([(u, u+40) for u in range(40)]), SETTINGS, WAITS)
        mapping = adaptive_partition(g, 4)
        self.assertEqual(set(mapping), set(g.ops))
        validate(g, g.schedule(mapping, 4)[0])

    def test_exact_budget_and_seeded_reproducibility(self):
        raw = fixture([(u, u+10) for u in range(10)])
        for features in [[], sorted(FEATURES)]:
            p, r, stats = solve_experimental(raw, SETTINGS, WAITS, 2, 8, 12, features)
            self.assertEqual(len(stats['evaluations']), 8)
            p2, r2, s2 = solve_experimental(raw, SETTINGS, WAITS, 2, 8, 12, features)
            self.assertEqual(p, p2)
            self.assertEqual(r['makespan'], r2['makespan'])
            self.assertLessEqual(r['makespan'], stats['singlecore_makespan'])
            self.assertEqual(stats['local_cost_conflicts'], 0)

    def test_official_errors_are_not_silently_swallowed(self):
        from unittest.mock import patch
        with patch('multicore_cut_evaluate_problem_1.evaluate_scene_a', side_effect=ValueError('broken evaluator')):
            with self.assertRaisesRegex(ValueError, 'broken evaluator'):
                solve_experimental(fixture([(0, 1)]), SETTINGS, WAITS, 2, 4)

    def test_single_evaluation_budget_stops_after_fallback(self):
        _, _, stats = solve_experimental(fixture([(0, 1)]), SETTINGS, WAITS, 4, 1, 0, FEATURES)
        self.assertEqual(len(stats['evaluations']), 1)
        self.assertTrue(stats['budget_exhausted'])

    def test_cross_core_slack_includes_1000_cycle_wait(self):
        g = CostGraph(fixture([(0, 1)]), SETTINGS, WAITS)
        plan = {'node_to_subgraph': {'0': 0, '1': 1}, 'core_schedules': [[0], [1]]}
        result = {'makespan': 1010, 'per_core_timeline': [
            {'tasks': [{'task_id': 0, 'start': 0, 'end': 5, 'duration': 5}]},
            {'tasks': [{'task_id': 1, 'start': 1005, 'end': 1010, 'duration': 5}]}]}
        self.assertEqual(task_slacks(g, plan, result), {0: 0, 1: 0})


if __name__ == '__main__':
    unittest.main()
