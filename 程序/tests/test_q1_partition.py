import unittest
from test_q1 import fixture, SETTINGS, WAITS, evaluate
from q1_solver import Graph, validate
from q1_partition import shared_pairs, shared_coarsen, repair
from q1_experimental import solve_experimental


class PartitionTests(unittest.TestCase):
    def test_external_input_affinity_and_safe_merge(self):
        raw = fixture([(0, 2), (1, 3)])
        for op in raw['ops']:
            op['cycles'] = 1
        raw['tensors'].append({'id': 900, 'pos': 'DDR', 'size': 60000})
        raw['edges'] += [{'source': 900, 'target': 0}, {'source': 900, 'target': 1}]
        g = Graph(raw, SETTINGS, WAITS)
        mapping = {u: u for u in g.ops}
        self.assertEqual(shared_pairs(g, mapping)[0, 1], 60000)
        merged = shared_coarsen(g, mapping, 2)
        self.assertEqual(set(merged), set(mapping))
        validate(g, g.schedule(merged, 2)[0])
        self.assertGreater(g.shared_input_stats['accepted'], 0)
        before = evaluate(raw, g.schedule(mapping, 2)[0])
        after = evaluate(raw, g.schedule(merged, 2)[0])
        self.assertLess(after['data_movement_bytes']['scheduled_copy_bytes'],
                        before['data_movement_bytes']['scheduled_copy_bytes'])

    def test_split_keeps_unaffected_core_and_order(self):
        raw = fixture([(0, 1), (2, 3), (4, 5)])
        g = Graph(raw, SETTINGS, WAITS)
        plan = {'node_to_subgraph': {'0': 0, '1': 0, '2': 1, '3': 1, '4': 2, '5': 2},
                'core_schedules': [[0, 2], [1]]}
        trial = repair(g, plan, {0: 0, 1: 3, 2: 1, 3: 1, 4: 2, 5: 2})
        self.assertEqual(trial['core_schedules'], [[0, 3, 2], [1]])
        self.assertGreater(evaluate(raw, trial)['makespan'], 0)
        # Merging separated nodes of a chain must be rejected.
        chain = Graph(fixture([(0, 1), (1, 2)]), SETTINGS, WAITS)
        with self.assertRaises(ValueError):
            repair(chain, {'node_to_subgraph': {'0': 0, '1': 1, '2': 2},
                           'core_schedules': [[0, 1, 2]]}, {0: 0, 1: 1, 2: 0})

    def test_protected_partition_attempts_and_repair_prefix(self):
        raw = fixture([(u, u+10) for u in range(10)])
        base = ['local_cost', 'critical', 'insertion', 'comm_rank', 'partition_guard']
        histories = []
        for extra in ([], ['local_repair'], ['shared_input']):
            _, result, stats = solve_experimental(raw, SETTINGS, WAITS, 4, 12, 0, base+extra)
            self.assertEqual(stats['official_calls'], 12)
            self.assertEqual(stats['protected_grain_attempts'], [.5, 1., 2., .25])
            self.assertEqual(result['makespan'], min(r['makespan'] for r in stats['evaluations']))
            histories.append(stats['evaluations'])
        prefix = lambda h: [(r['candidate'], r['makespan']) for r in h
                            if r['candidate'] in {'single_task', 'greedy', 'multilevel',
                                                  'grain_0.5', 'grain_1.0', 'grain_2.0', 'grain_0.25'}]
        self.assertEqual(prefix(histories[0]), prefix(histories[1]))
        with self.assertRaises(ValueError):
            solve_experimental(raw, SETTINGS, WAITS, 4, 7, 0, base)
