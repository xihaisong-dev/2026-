import unittest
from test_q1 import fixture,SETTINGS,WAITS,evaluate
from q1_pipe_event import replay_network,event_time
from q1_critical_chain import candidates,critical_chain
from q1_experimental import CostGraph,solve_experimental
from q1_local_rank import LocalRank
from q1_solver import validate


class PipeEventTests(unittest.TestCase):
    def test_copy_delay_does_not_stall_independent_compute(self):
        pred={0:{},1:{},2:{},3:{0:0}}
        base={0:10.,1:100.,2:10.,3:1.}
        value,info=replay_network([0,1,2,3],pred,base,{0,2})
        self.assertEqual(value,100)
        self.assertEqual(info['passes'],3)
        # Relaxed approximation intentionally does not impersonate exact sharing.
        value,_=replay_network([0,2,3],{0:{},2:{},3:{0:0}},
                               {0:10.,2:10.,3:1.},{0,2})
        self.assertAlmostEqual(value,19.75)
        serial,_=replay_network([0,1],{0:{},1:{0:7}},{0:10.,1:20.},set())
        self.assertEqual(serial,37)

    def test_real_prepared_graph(self):
        raw=fixture([(0,1),(0,2),(1,3),(2,3)])
        g=CostGraph(raw,SETTINGS,WAITS,True)
        plan={'node_to_subgraph':{str(u):0 for u in g.ops},'core_schedules':[[0]]}
        ranker=LocalRank(raw,g,event=True)
        score,_,_=ranker.score(plan)
        self.assertGreater(score,0)
        self.assertEqual(ranker.stats()['global_evaluations'],0)
        self.assertEqual(ranker.stats()['event_passes'],3)
        tasks,_,_,_=ranker.preparer._build(raw,plan,g.bandwidth,g.capacity)
        # A memory/dependency cycle in prepared input must fail closed.
        u,v=tasks[0]['seq'][:2]
        tasks[0]['op_preds'][u].add(v);tasks[0]['op_preds'][v].add(u)
        with self.assertRaises(ValueError):event_time(g,plan,tasks)

    def test_joint_chain_legality_and_budget(self):
        raw=fixture([(i,i+1) for i in range(14)])
        for op in raw['ops']:op['cycles']=100
        g=CostGraph(raw,SETTINGS,WAITS,True)
        plan={'node_to_subgraph':{str(u):u for u in g.ops},
              'core_schedules':[[u for u in sorted(g.ops) if u%3==c] for c in range(3)]}
        result=evaluate(raw,plan)
        chain,_,info=critical_chain(g,plan,result)
        self.assertEqual(info['profile_path'],result['makespan'])
        proposals=list(candidates(g,plan,result,3))
        self.assertTrue(proposals)
        self.assertLessEqual(g.chain_stats[-1]['probes'],12)
        for _,p in proposals:
            validate(g,p)
            self.assertEqual(set(p['node_to_subgraph']),set(plan['node_to_subgraph']))
        features=['local_cost','critical','insertion','comm_rank','partition_guard',
                  'region','exact_region','event_rank','chain_joint']
        _,result,stats=solve_experimental(raw,SETTINGS,WAITS,3,12,0,features)
        self.assertEqual(stats['official_calls'],12)
        self.assertEqual(result['makespan'],min(x['makespan'] for x in stats['evaluations']))

    def test_late_repair_reserves_all_grains(self):
        raw=fixture([(i,i+8) for i in range(8)])
        features=['local_cost','critical','insertion','comm_rank','partition_guard',
                  'region','exact_region','event_rank','chain_joint','late_chain']
        _,result,stats=solve_experimental(raw,SETTINGS,WAITS,3,12,0,features)
        self.assertEqual(stats['official_calls'],12)
        self.assertEqual(stats['protected_grain_attempts'],[.5,1.,2.,.25])
        self.assertTrue(any(x['candidate'].startswith('random_') for x in stats['evaluations'][:-1]))
        self.assertIsNotNone(stats['late_region_start'])
        self.assertEqual(stats['late_region_start']['evaluation_index'],11)
        self.assertEqual(stats['late_region_start']['grain_attempts'],[.5,1.,2.,.25])
        self.assertEqual(result['makespan'],min(x['makespan'] for x in stats['evaluations']))
