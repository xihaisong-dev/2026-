import copy
import unittest
from test_q1 import fixture, SETTINGS, WAITS, evaluate
from q1_exact_placement import PartitionEvaluator, candidates
from q1_experimental import CostGraph


class ExactPlacementTests(unittest.TestCase):
    def test_full_output_matches_after_moves_reorders_and_core_change(self):
        raw = fixture([(0, 2), (1, 3)])
        engine = PartitionEvaluator(raw, 60, SETTINGS['capacity'], 1000, 100)
        import multicore_cut_evaluate_problem_1 as official
        original_builder = official._build_scene_a_tasks
        for schedules in ([[0, 2], [1, 3]], [[0, 1], [2, 3]],
                          [[1, 0], [3, 2]], [[0], [1], [2], [3]], [[0, 1, 2, 3]]):
            plan = {'node_to_subgraph': {str(u): u for u in range(4)},
                    'core_schedules': schedules}
            result = engine.evaluate(plan)
            self.assertEqual(result, evaluate(raw, plan))
            result['data_movement_bytes']['added_copy_bytes'] = -1
        self.assertEqual(engine.misses, 1)
        self.assertEqual(engine.hits, 4)
        self.assertIs(official._build_scene_a_tasks, original_builder)

    def test_invalid_plan_on_hit_and_partition_ids_do_not_alias(self):
        raw = fixture([(0, 1), (2, 3)])
        engine = PartitionEvaluator(raw, 60, SETTINGS['capacity'], 1000, 100)
        plan = {'node_to_subgraph': {str(u): u for u in range(4)},
                'core_schedules': [[0, 1], [2, 3]]}
        engine.evaluate(plan)
        invalid = copy.deepcopy(plan)
        invalid['core_schedules'] = [[1, 2], [3, 0]]
        with self.assertRaises(Exception):
            engine.evaluate(invalid)
        renamed = {'node_to_subgraph': {str(u): u+10 for u in range(4)},
                   'core_schedules': [[10, 11], [12, 13]]}
        self.assertEqual(engine.evaluate(renamed), evaluate(raw, renamed))
        self.assertEqual(engine.misses, 2)

    def test_candidates_preserve_partition_and_budget(self):
        raw = fixture([(u, u+6) for u in range(6)])
        g = CostGraph(raw, SETTINGS, WAITS, True)
        plan = {'node_to_subgraph': {str(u): u for u in range(12)},
                'core_schedules': [[0, 1, 2, 6, 7, 8], [3, 4, 5, 9, 10, 11]]}
        result = evaluate(raw, plan)
        g.observe(plan, result)
        pool = candidates(g, plan, result, 8)
        self.assertLessEqual(len(pool), 8)
        self.assertEqual(pool, candidates(g, plan, result, 8))
        engine = PartitionEvaluator(raw, 60, SETTINGS['capacity'], 1000, 100)
        for _, trial, _ in pool:
            self.assertEqual(trial['node_to_subgraph'], plan['node_to_subgraph'])
            self.assertEqual(engine.evaluate(trial), evaluate(raw, trial))
