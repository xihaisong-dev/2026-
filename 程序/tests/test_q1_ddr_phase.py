import unittest
from test_q1 import fixture,SETTINGS,WAITS,evaluate
from q1_experimental import CostGraph,solve_experimental
from q1_ddr_phase import phase_time,profile
from q1_local_rank import LocalRank


class PhaseTests(unittest.TestCase):
    def setUp(self):
        self.g = CostGraph(fixture([(0,1),(2,3)]),SETTINGS,WAITS,True)
        self.plan = {'node_to_subgraph':{'0':0,'1':0,'2':1,'3':1},'core_schedules':[[0],[1]]}

    def test_analytic_overlap_and_offsets(self):
        self.assertEqual(phase_time(self.g,self.plan,{0:[(10,1)],1:[(10,1)]}),20)
        self.assertEqual(phase_time(self.g,self.plan,{0:[(10,0)],1:[(10,1)]}),10)
        # Same total DDR work, no overlap.
        self.assertEqual(phase_time(self.g,self.plan,{0:[(10,1),(10,0)],1:[(10,0),(10,1)]}),20)
        # Internal two-COPY sharing must not be charged a second time.
        self.assertEqual(phase_time(self.g,self.plan,{0:[(10,2)],1:[(10,0)]}),10)
        serial=dict(self.plan,core_schedules=[[0,1],[]])
        self.assertEqual(phase_time(self.g,serial,{0:[(10,1)],1:[(10,1)]}),120)

    def test_profile_budget_and_no_feedback(self):
        raw=fixture([(i,i+1) for i in range(50)])
        g=CostGraph(raw,SETTINGS,WAITS,True)
        ranker=LocalRank(raw,g,True)
        plan={'node_to_subgraph':{str(u):0 for u in g.ops},'core_schedules':[[0]]}
        value,_,_=ranker.score(plan)
        tasks,_,_,_=ranker.preparer._build(raw,plan,g.bandwidth,g.capacity)
        phases=profile(tasks[0],limit=4)
        self.assertLessEqual(len(phases),4)
        self.assertAlmostEqual(sum(x[0] for x in phases),tasks[0]['step3']['makespan'])
        self.assertAlmostEqual(value,evaluate(raw,plan)['makespan'])
        self.assertEqual(ranker.stats()['global_evaluations'],0)

    def test_solver_budget(self):
        raw=fixture([(i,i+8) for i in range(8)])
        features=['local_cost','critical','insertion','comm_rank','partition_guard','region','exact_region','phase_rank']
        _,result,s=solve_experimental(raw,SETTINGS,WAITS,3,12,0,features)
        self.assertEqual(s['official_calls'],12)
        self.assertEqual(result['makespan'],min(e['makespan'] for e in s['evaluations']))
