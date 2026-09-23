import unittest
from test_q1 import fixture, SETTINGS, WAITS
from q1_structural_seeds import GraphModel
from q1_memory_routes import memory_pool, hybrid_pool, routed_candidates
from q1_solver import Graph, validate
from q1_experimental import solve_experimental
from q1_ablation import CONFIGS


class MemoryRouteTests(unittest.TestCase):
    def test_heavy_split_keeps_small_components_and_acyclic_order(self):
        raw=fixture([(i,i+1) for i in range(24)]+[(40,41),(50,51),(60,61)])
        m=GraphModel(raw,SETTINGS,WAITS)
        for name,plan in hybrid_pool(m,3):
            validate(Graph(raw,SETTINGS,WAITS),plan)
            for a,b in [(40,41),(50,51),(60,61)]:
                self.assertEqual(plan['node_to_subgraph'][str(a)],plan['node_to_subgraph'][str(b)])
            heavy={plan['node_to_subgraph'][str(i)] for i in range(25)}
            self.assertGreater(len(heavy),1);self.assertLessEqual(len(heavy),6)

    def test_memory_batches_preserve_every_component(self):
        raw=fixture([(i,i+30) for i in range(20)]);m=GraphModel(raw,SETTINGS,WAITS)
        pool=memory_pool(m,3);self.assertLessEqual(len(pool),3)
        for _,plan in pool:
            validate(Graph(raw,SETTINGS,WAITS),plan)
            for group in m.components:
                self.assertEqual(len({plan['node_to_subgraph'][str(u)] for u in group}),1)

    def test_routes_keep_budget_and_existing_eligible_result(self):
        raw=fixture([(i,i+30) for i in range(20)])
        base=solve_experimental(raw,SETTINGS,WAITS,3,12,0,CONFIGS['component_local_rank'])
        for name in ['component_memory','component_hybrid']:
            result=solve_experimental(raw,SETTINGS,WAITS,3,12,0,CONFIGS[name])
            self.assertEqual(result[0],base[0]);self.assertEqual(result[1],base[1])
        raw=fixture([(i,i+1) for i in range(24)]+[(40,41),(50,51),(60,61)])
        _,_,stats=solve_experimental(raw,SETTINGS,WAITS,3,12,0,CONFIGS['component_hybrid'])
        self.assertEqual(len(stats['evaluations']),12)
        self.assertEqual(stats['protected_grain_attempts'],[.5,1.,2.,.25])
        self.assertLessEqual(stats['structural_seed_stats']['evaluated'],1)
        self.assertEqual(stats['structural_seed_stats']['local_preparation']['global_evaluations'],0)


if __name__=='__main__':unittest.main()
