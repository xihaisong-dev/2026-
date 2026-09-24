"""Official B semantics, replay, deterministic bounded ablations, invalid plans."""
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from q2_evaluator import load,evaluate,fixed_reference
from q2_solver import SceneBGraph,base_bytes,solve,VARIANTS,order_plan,place
from test_q1 import fixture


class SceneBTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.settings,cls.delay,_=load()

    def test_same_core_subgraphs_do_not_force_roundtrip(self):
        raw=fixture([(0,1),(1,2)])
        whole={'node_to_subgraph':{str(i):0 for i in range(3)},'core_schedules':[[0]]}
        split={'node_to_subgraph':{str(i):i for i in range(3)},'core_schedules':[[0,1,2]]}
        a=evaluate(raw,whole,self.settings,self.delay);b=evaluate(raw,split,self.settings,self.delay)
        self.assertEqual(a['makespan'],b['makespan'])
        self.assertEqual(a['data_movement_bytes'],b['data_movement_bytes'])
        self.assertEqual(a['makespan'],fixed_reference(raw,self.settings)['makespan'])

    def test_fanout_once_per_consumer_core(self):
        raw=fixture([(0,1),(0,2)])
        together={'node_to_subgraph':{str(i):i for i in range(3)},'core_schedules':[[0],[1,2],[]]}
        apart={'node_to_subgraph':together['node_to_subgraph'],'core_schedules':[[0],[1],[2]]}
        g=SceneBGraph(raw,self.settings,self.delay)
        a=evaluate(raw,together,self.settings,self.delay);b=evaluate(raw,apart,self.settings,self.delay)
        self.assertEqual(len(a['cross_core_transfers']),1)
        self.assertEqual(len(b['cross_core_transfers']),2)
        self.assertEqual(b['data_movement_bytes']['partition_added_copy_bytes']-a['data_movement_bytes']['partition_added_copy_bytes'],120)
        for plan,result in [(together,a),(apart,b)]:
            self.assertEqual(base_bytes(g,plan),result['data_movement_bytes']['scheduled_copy_bytes'])

    def test_return_to_core_is_legal_not_core_contraction(self):
        raw=fixture([(0,1),(1,2)])
        plan={'node_to_subgraph':{str(i):i for i in range(3)},'core_schedules':[[0,2],[1]]}
        r=evaluate(raw,plan,self.settings,self.delay)
        self.assertEqual(len(r['cross_core_transfers']),2)
        invalid={'node_to_subgraph':{'0':0,'1':1,'2':0},'core_schedules':[[0],[1]]}
        with self.assertRaises((ValueError,RuntimeError)):evaluate(raw,invalid,self.settings,self.delay)

    def test_variants_determinism_budget_and_serialized_replay(self):
        raw=fixture([(0,1),(0,2),(1,3),(2,3),(3,4),(2,5)])
        for variant in VARIANTS:
            a,r,s=solve(raw,self.settings,self.delay,2,budget=8,seed=7,variant=variant)
            b,t,u=solve(raw,self.settings,self.delay,2,budget=8,seed=7,variant=variant)
            self.assertEqual(a,b);self.assertEqual(r,t)
            self.assertEqual(r,evaluate(raw,json.loads(json.dumps(a)),self.settings,self.delay))
            self.assertEqual(s['official_calls'],8);self.assertEqual(s['features'],list(VARIANTS[variant]))
            self.assertEqual([x['plan_sha256'] for x in s['evaluations']],[x['plan_sha256'] for x in u['evaluations']])
            self.assertLessEqual(r['makespan'],s['evaluations'][0]['makespan'])

    def test_lifetime_order_releases_shared_tensor_before_new_branch(self):
        # Two independent chains: consuming the already-live large tensor
        # should precede materializing another large tensor.
        raw=fixture([(0,2),(1,3)])
        for t in raw['tensors']:t['size']=60000 if t['id'] in (100,101) else 60
        g=SceneBGraph(raw,self.settings,self.delay)
        p=order_plan(g,{v:v for v in g.ops},{v:0 for v in g.ops},1,lifetime=True,weight=10)
        seq=p['core_schedules'][0]
        self.assertEqual(seq,[0,2,1,3])
        evaluate(raw,p,self.settings,self.delay)

    def test_parameters_rejected(self):
        with self.assertRaises(ValueError):solve(fixture([(0,1)]),self.settings,self.delay,2,params={'ready_window':0})

    def test_communication_placement_reuses_external_input(self):
        raw={'ops':[{'id':i,'op':'CUSTOM','pipe':'PIPE_V','cycles':500} for i in (0,1)],
             'tensors':[{'id':100,'pos':'UB','size':60000}],
             'edges':[{'source':100,'target':i} for i in (0,1)]}
        g=SceneBGraph(raw,self.settings,self.delay);mapping={0:0,1:1}
        plain=place(g,mapping,2,False);aware=place(g,mapping,2,True)
        self.assertNotEqual(plain[0],plain[1]);self.assertEqual(aware[0],aware[1])
        a=order_plan(g,mapping,plain,2);b=order_plan(g,mapping,aware,2)
        self.assertEqual(base_bytes(g,a)-base_bytes(g,b),60000)
        for p in (a,b):evaluate(raw,p,self.settings,self.delay)

    def test_direct_operation_edge_bytes(self):
        raw={'ops':[{'id':i,'op':'CUSTOM','pipe':'PIPE_V','cycles':500} for i in (0,1)],
             'tensors':[],'edges':[{'source':0,'target':1,'data_size':60}]}
        plan={'node_to_subgraph':{'0':0,'1':1},'core_schedules':[[0],[1]]}
        r=evaluate(raw,plan,self.settings,self.delay)
        self.assertEqual(base_bytes(SceneBGraph(raw,self.settings,self.delay),plan),120)
        self.assertEqual(r['data_movement_bytes']['scheduled_copy_bytes'],120)


if __name__=='__main__':unittest.main()
