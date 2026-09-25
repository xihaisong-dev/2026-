import random,unittest
from test_q1 import fixture,SETTINGS,WAITS,evaluate
from q1_experimental import CostGraph
from q1_timed_candidates import components
from q1_staged_moves import profile,weights,timeline_move
from q1_solver import validate

class MoveTests(unittest.TestCase):
    def test_structural_features_do_not_use_case_identifier(self):
        raw=fixture([(0,1),(1,2),(2,3)]);g=CostGraph(raw,SETTINGS,WAITS,False)
        p=profile(g,components(g))
        self.assertEqual(p['chain_work_fraction'],1)
        self.assertEqual(p['largest_component_fraction'],1)
        w=weights(p,['frontier','boundary','list_order','timeline_joint'])
        self.assertGreater(w['boundary'],w['frontier'])

    def test_timeline_moves_cover_operations_and_keep_valid_candidates(self):
        raw=fixture([(0,1),(1,2),(2,3),(4,5),(5,6)])
        g=CostGraph(raw,SETTINGS,WAITS,False);g.fast_costs=True
        p={'node_to_subgraph':{str(i):i for i in range(7)},'core_schedules':[[0,1,2,3],[4,5,6]]}
        r=evaluate(raw,p);legal=0
        for i in range(12):
            try:q=timeline_move(g,p,r,2,random.Random(i),i);validate(g,q)
            except (ValueError,RuntimeError):continue
            self.assertEqual(set(map(int,q['node_to_subgraph'])),set(g.ops));legal+=1
        self.assertGreater(legal,0)

if __name__=='__main__':unittest.main()
