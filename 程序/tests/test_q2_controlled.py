import unittest,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from q1_io import PROCESSED
from q1_structural_seeds import GraphModel,_heft_plan
from q2_solver import SceneBGraph
from q2_evaluator import load,key
from q2_controlled import heft,mixed_proposals


class ControlledTest(unittest.TestCase):
    def test_reference_heft_equivalence(self):
        settings,delay,_=load()
        for i in [12,48]:
            raw=json.loads((PROCESSED/f'data/case_{i:03}.json').read_text(encoding='utf-8'))
            m=GraphModel(raw,settings,dict(task_cross_core_wait_cycles=delay,task_same_core_wait_cycles=0));g=SceneBGraph(raw,settings,delay)
            for groups in [m.chain_groups(),m.connected_groups({u:m.depth[u]//8 for u in m.ids})]:
                for k in [2,5]:self.assertEqual(heft(m,g,groups,k),_heft_plan(m,groups,k,2))

    def test_mixed_preserves_duplicate_budget_slots(self):
        p={'node_to_subgraph':{'1':0},'core_schedules':[[0],[]]}
        a=[dict(plan=p,move={'ordinary':j}) for j in range(4)]
        b=[dict(plan=p,move={'guided':j}) for j in range(4)]
        self.assertEqual(mixed_proposals(a,b,p),a[:2]+b[:2])
        self.assertEqual(len(mixed_proposals([],[],p)),4)


if __name__=='__main__':unittest.main()
