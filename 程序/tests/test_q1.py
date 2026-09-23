"""官方语义回归测试；需先运行主程序 prepare。"""
from pathlib import Path
import json
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from q1_io import official, verify, write_json, sha
official()
from q1_solver import Graph, solve, validate, greedy_partition
from multicore_cut_evaluate_problem_1 import evaluate_scene_a
from singlecore_evaluate import evaluate_singlecore

SETTINGS = {'bandwidth': 60, 'capacity': {'L1': 524288, 'UB': 131072}}
WAITS = {'task_cross_core_wait_cycles': 1000, 'task_same_core_wait_cycles': 100}


def fixture(edges):
    """每个生产者一个张量，支持多消费者；算子周期足够摊薄同步。"""
    ids = sorted({u for edge in edges for u in edge})
    tensors, links = [], []
    for u in ids:
        tensors.append({'id': 100 + u, 'pos': 'UB', 'size': 60})
        links.append({'source': u, 'target': 100 + u})
    for u, v in edges:
        links.append({'source': 100 + u, 'target': v})
    return {'ops': [{'id': u, 'op': 'CUSTOM', 'pipe': 'PIPE_V', 'cycles': 10000} for u in ids],
            'tensors': tensors, 'edges': links}


def evaluate(graph, plan):
    return evaluate_scene_a(graph, plan, 60, SETTINGS['capacity'], 1000, 100)


class Q1Tests(unittest.TestCase):
    def test_shared_tensor_is_read_once_per_consumer_task(self):
        raw = fixture([(0, 1), (0, 2)])
        plan = {'node_to_subgraph': {'0': 0, '1': 1, '2': 1}, 'core_schedules': [[0, 1]]}
        result = evaluate(raw, plan)
        # t0: one write + one read, final t1/t2: one write each = 240 bytes.
        self.assertEqual(result['data_movement_bytes']['scheduled_copy_bytes'], 240)
        g = Graph(raw, SETTINGS, WAITS)
        self.assertEqual(g.costs({0: 0, 1: 1, 2: 1})[1], 240)
        timeline = result['per_core_timeline'][0]['tasks']
        self.assertEqual(timeline[1]['start'] - timeline[0]['end'], 100)

    def test_cross_core_wait_not_substituted_for_transfer(self):
        raw = fixture([(0, 1)])
        result = evaluate(raw, {'node_to_subgraph': {'0': 0, '1': 1}, 'core_schedules': [[0], [1]]})
        a, b = [x['tasks'][0] for x in result['per_core_timeline']]
        self.assertEqual(b['start'] - a['end'], 1000)
        self.assertGreater(b['duration'], 10000)

    def test_joint_core_order_cycle_rejected(self):
        g = Graph(fixture([(0, 1), (2, 3)]), SETTINGS, WAITS)
        plan = {'node_to_subgraph': {str(i): i for i in range(4)}, 'core_schedules': [[1, 2], [3, 0]]}
        with self.assertRaises((ValueError, RuntimeError)):
            validate(g, plan)

    def test_nonconvex_partition_rejected(self):
        g = Graph(fixture([(0, 1), (1, 2)]), SETTINGS, WAITS)
        with self.assertRaises(ValueError):
            g.schedule({0: 0, 1: 1, 2: 0}, 2)

    def test_three_methods_and_determinism(self):
        g = Graph(fixture([(0, 1), (0, 2), (1, 3), (2, 3)]), SETTINGS, WAITS)
        for method in ['greedy', 'multilevel', 'alns']:
            p, r, s = solve(g, 2, method, budget=4, seed=9, block_size=1)
            validate(g, p)
            self.assertLessEqual(r['makespan'], s['singlecore_makespan'])
            self.assertLessEqual(s['search_evaluations'], 4)
            p2, r2, _ = solve(g, 2, method, budget=4, seed=9, block_size=1)
            self.assertEqual(p, p2)
            self.assertEqual(r['makespan'], r2['makespan'])

    def test_single_core_matches_official_baseline(self):
        raw = fixture([(0, 1), (0, 2)])
        _, result, stats = solve(Graph(raw, SETTINGS, WAITS), 1)
        reference = evaluate_singlecore(raw, 60, SETTINGS['capacity'], 1000, 100)
        self.assertEqual(result['makespan'], reference['makespan'])
        self.assertEqual(stats['speedup'], 1)
        self.assertEqual(len(stats['evaluations']), 1)

    def test_refinement_preserves_incumbent_and_budget(self):
        g = Graph(fixture([(0, 1), (0, 2), (1, 3), (2, 3)]), SETTINGS, WAITS)
        _, before, _ = solve(g, 2, budget=3, seed=7, block_size=2)
        p, after, stats = solve(g, 2, budget=3, seed=7, block_size=2, refine_budget=5)
        validate(g, p)
        self.assertLessEqual(after['makespan'], before['makespan'])
        self.assertLessEqual(stats['refinement_evaluations'], 5)
        p2, _, _ = solve(g, 2, budget=3, seed=7, block_size=2, refine_budget=5)
        self.assertEqual(p, p2)

    def test_wide_graph_does_not_fragment_into_single_ops(self):
        raw = fixture([(u, u + 40) for u in range(40)])
        g = Graph(raw, SETTINGS, WAITS)
        mapping = greedy_partition(g, cores=2, block_size=8)
        self.assertEqual(len(set(mapping.values())), 10)
        validate(g, g.schedule(mapping, 2)[0])

    def test_hash_tampering_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'input.json').write_bytes(b'original')
            write_json(root / 'manifest.json', {'files': {'input.json': sha(b'original')}})
            verify(root)
            (root / 'input.json').write_bytes(b'modified')
            with self.assertRaises(ValueError):
                verify(root)

    def test_result_bytes_use_git_stable_lf(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'result.json'
            write_json(path, {'x': [1, 2]})
            self.assertNotIn(b'\r\n', path.read_bytes())
            self.assertEqual(json.loads(path.read_bytes()), {'x': [1, 2]})


if __name__ == '__main__':
    unittest.main()
