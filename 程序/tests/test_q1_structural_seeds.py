import unittest
from test_q1 import fixture, SETTINGS, WAITS, evaluate
from q1_solver import Graph, validate
from q1_structural_seeds import GraphModel, initial_candidates, canonical_key, _component_batch_plan
from q1_experimental import solve_experimental
from q1_ablation import CONFIGS


class StructuralSeedTests(unittest.TestCase):
    def test_components_remain_whole_and_batches_preserve_large_component(self):
        raw = fixture([(u, u+30) for u in range(30)])
        graph = Graph(raw, SETTINGS, WAITS)
        model = GraphModel(raw, SETTINGS, WAITS)
        plans, info = initial_candidates(raw, SETTINGS, WAITS, 3, {'components', 'batches'})
        self.assertTrue(info['batch_eligible'])
        for _, plan in plans + [('tiny_batches', _component_batch_plan(model, 3, 1))]:
            validate(graph, plan)
            for component in model.components:
                self.assertEqual(len({plan['node_to_subgraph'][str(u)] for u in component}), 1)
            self.assertGreater(evaluate(raw, plan)['makespan'], 0)

    def test_depth_partition_and_schedule_stay_acyclic_on_branch_join(self):
        edges = [(u, u+1) for u in range(24)] + [(0, 30), (30, 24)]
        raw = fixture(edges)
        graph = Graph(raw, SETTINGS, WAITS)
        plans, info = initial_candidates(raw, SETTINGS, WAITS, 4, {'depth'})
        self.assertTrue(info['dominant_component'])
        self.assertEqual([name for name, _ in plans], ['depth8', 'depth16', 'depth4'])
        for _, plan in plans:
            validate(graph, plan)
            self.assertGreater(evaluate(raw, plan)['makespan'], 0)

    def test_dedup_ignores_labels_but_not_core_mapping_or_order(self):
        p = {'node_to_subgraph': {'0': 3, '1': 7}, 'core_schedules': [[3], [7]]}
        renamed = {'node_to_subgraph': {'0': 10, '1': 20}, 'core_schedules': [[10], [20]]}
        swapped = {'node_to_subgraph': {'0': 10, '1': 20}, 'core_schedules': [[20], [10]]}
        self.assertEqual(canonical_key(p), canonical_key(renamed))
        self.assertNotEqual(canonical_key(p), canonical_key(swapped))

    def test_same_budget_initial_prefix_and_four_grains_survive(self):
        raw = fixture([(u, u+30) for u in range(30)])
        _, base, stats0 = solve_experimental(raw, SETTINGS, WAITS, 3, 12, 0, CONFIGS['shared_region'])
        for name in ['seed_components', 'seed_batches', 'seed_depth', 'seed_combined']:
            _, result, stats = solve_experimental(raw, SETTINGS, WAITS, 3, 12, 0, CONFIGS[name])
            self.assertEqual(len(stats['evaluations']), 12)
            self.assertEqual(stats['protected_grain_attempts'], [.5, 1., 2., .25])
            self.assertLessEqual(stats['structural_seed_stats']['evaluated'], 4)
            self.assertEqual([(r['candidate'], r['makespan']) for r in stats['evaluations'][:3]],
                             [(r['candidate'], r['makespan']) for r in stats0['evaluations'][:3]])
            self.assertEqual(result['makespan'], min(r['makespan'] for r in stats['evaluations']))
        # Ineligible depth-only family must leave the full search trajectory alone.
        _, result, stats = solve_experimental(raw, SETTINGS, WAITS, 3, 12, 0, CONFIGS['seed_depth'])
        self.assertEqual(result['makespan'], base['makespan'])
        self.assertEqual([(r['candidate'], r['makespan']) for r in stats['evaluations']],
                         [(r['candidate'], r['makespan']) for r in stats0['evaluations']])

    def test_invalid_structural_budget_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Structural seeds'):
            solve_experimental(fixture([(0,1)]), SETTINGS, WAITS, 2, 11, 0, CONFIGS['seed_combined'])


if __name__ == '__main__':
    unittest.main()
