"""Structural invariants for the new work-based partition proposals."""
import json,random,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from q1_io import PROCESSED,official
from q1_experimental import CostGraph
from q1_solver import validate
from q1_timed_candidates import components,frontier_mapping,packing,schedule

class CandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        mod=official()
        from evaluation_validation import read_evaluation_config
        config=str(PROCESSED/'data/config.txt')
        raw=json.loads((PROCESSED/'data/case_006.json').read_text(encoding='utf-8-sig'))
        cls.g=CostGraph(raw,read_evaluation_config(config),mod.read_scene_a_config(config),enabled=False)

    def test_frontier_cover_and_acyclic_across_grains(self):
        for seed in range(6):
            rng=random.Random(seed);mapping=frontier_mapping(self.g,5,rng,seed)
            self.assertEqual(set(mapping),set(self.g.ops))
            groups,_,_,order=self.g.view(mapping)
            self.assertEqual(len(groups),len(order))
            validate(self.g,schedule(self.g,mapping,5,rng,seed))

    def test_whole_component_packing_never_cuts_component(self):
        groups=components(self.g)
        for seed in range(8):
            plan=packing(self.g,groups,5,random.Random(seed),seed)
            validate(self.g,plan)
            self.assertEqual(set(map(int,plan['node_to_subgraph'])),set(self.g.ops))
            for group in groups:
                self.assertEqual(len({plan['node_to_subgraph'][str(u)] for u in group}),1)

    def test_reproducible_proposal_for_seed(self):
        a=frontier_mapping(self.g,3,random.Random(42),2)
        b=frontier_mapping(self.g,3,random.Random(42),2)
        self.assertEqual(a,b)

    def test_bootstrap_task_cap_preserves_acyclic_cover(self):
        mapping=frontier_mapping(self.g,5,random.Random(0),0,target_groups=1,max_ops=16)
        groups,_,_,_=self.g.view(mapping)
        self.assertTrue(all(len(nodes)<=16 for nodes in groups.values()))
        self.assertEqual(set(mapping),set(self.g.ops))

    def test_multicore_initial_is_not_singlecore_reference(self):
        from q1_experimental import solve_experimental
        mod=official()
        from evaluation_validation import read_evaluation_config
        config=str(PROCESSED/'data/config.txt')
        raw=json.loads((PROCESSED/'data/case_006.json').read_text(encoding='utf-8-sig'))
        plan=packing(self.g,components(self.g),5,random.Random(0),0)
        result,_,stats=solve_experimental(raw,read_evaluation_config(config),mod.read_scene_a_config(config),
            cores=5,evaluation_budget=2,initial_plan=plan)
        validate(self.g,result)
        self.assertIsNone(stats['singlecore_makespan'])
        self.assertIsNone(stats['speedup'])

if __name__=='__main__':unittest.main()
