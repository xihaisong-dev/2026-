import unittest
from test_q1 import fixture,SETTINGS,WAITS,evaluate
from q1_experimental import CostGraph,solve_experimental
from q1_exact_placement import PartitionEvaluator
from q1_fast_evaluator import evaluator
from q1_local_rank import LocalRank
from q1_structural_seeds import guarded_component_candidate,canonical_key
from q1_opportunity import compare_event_profiles
from q1_ablation import CONFIGS

class EventReuseTests(unittest.TestCase):
    def test_one_off_global_build_does_not_evict_prepared_partition(self):
        raw=fixture([(0,1),(2,3)]);g=CostGraph(raw,SETTINGS,WAITS,False)
        p={'node_to_subgraph':{'0':0,'1':0,'2':1,'3':1},'core_schedules':[[0],[1]]}
        q={'node_to_subgraph':{'0':0,'1':1,'2':2,'3':3},'core_schedules':[[0,1],[2,3]]}
        prep=PartitionEvaluator(raw,g.bandwidth,g.capacity,g.cross,g.same,max_partitions=1,cache_on_evaluate=False)
        rank=LocalRank(raw,g,event=True,preparer=prep)
        before=rank.score(p)
        self.assertEqual(prep.evaluate(q),evaluate(raw,q))
        self.assertEqual(prep.uncached_builds,1)
        self.assertEqual(prep.evaluate(p),evaluate(raw,p))
        self.assertEqual(rank.score(p),before)
        self.assertEqual(prep.misses,1)
        self.assertEqual(prep.hits,2)

    def test_shared_preparation_matches_original_and_does_not_cache_global_score(self):
        raw=fixture([(i,i+8) for i in range(8)])
        g=CostGraph(raw,SETTINGS,WAITS,False)
        plan={'node_to_subgraph':{str(o['id']):o['id']%2 for o in raw['ops']},'core_schedules':[[0],[1]]}
        prep=PartitionEvaluator(raw,g.bandwidth,g.capacity,g.cross,g.same,backend_engine=evaluator())
        rank=LocalRank(raw,g,event=True,preparer=prep,reuse_scores=True)
        v,_,_=rank.score(plan)
        self.assertEqual(prep.evaluations,0)
        self.assertEqual(prep.evaluate(plan),evaluate(raw,plan))
        self.assertEqual(prep.evaluate(plan),evaluate(raw,plan))
        self.assertEqual(prep.evaluations,2);self.assertEqual(prep.misses,1)
        _,decision=compare_event_profiles(raw,g,plan,plan,rank)
        self.assertEqual(decision['local_preparation_calls'],0)
        self.assertEqual(decision['score_cache_hits'],2)
        self.assertEqual(decision['candidate_event'],v)
        self.assertEqual(prep.evaluations,2)

    def test_cached_rank_returns_independent_data_and_order_is_in_key(self):
        raw=fixture([(0,1),(2,3)]);g=CostGraph(raw,SETTINGS,WAITS,False)
        rank=LocalRank(raw,g,event=True,reuse_scores=True)
        p={'node_to_subgraph':{'0':0,'1':0,'2':1,'3':1},'core_schedules':[[0,1],[]]}
        v,d,t=rank.score(p);d.clear()
        self.assertTrue(rank.score(p)[1]);self.assertEqual(rank.score_hits,1)
        p['core_schedules']=[[1,0],[]];rank.score(p)
        self.assertEqual(rank.calls,2);self.assertEqual(rank.preparer.misses,1)

    def test_event_sort_preserves_component_pool_and_tie_rule(self):
        raw=fixture([(u,u+30) for u in range(30)])
        _,local=guarded_component_candidate(raw,SETTINGS,WAITS,3,max_candidates=2,ranking='local')
        _,event=guarded_component_candidate(raw,SETTINGS,WAITS,3,max_candidates=2,ranking='event')
        self.assertEqual({r['candidate'] for r in local['ranked']},{r['candidate'] for r in event['ranked']})
        self.assertEqual([r['event_prediction'] for r in event['ranked']],sorted(r['event_prediction'] for r in event['ranked']))

    def test_cache_switch_preserves_trajectory_and_official_result(self):
        for raw in [fixture([(u,u+30) for u in range(30)]),fixture([(i,i+1) for i in range(24)]+[(40,41),(50,51),(60,61)])]:
            for a,b in [('routes_event_rank','routes_event_reuse'),('routes_event_guarded','routes_gate_reuse')]:
                first=solve_experimental(raw,SETTINGS,WAITS,3,12,0,CONFIGS[a],evaluator_backend='counter')
                second=solve_experimental(raw,SETTINGS,WAITS,3,12,0,CONFIGS[b],evaluator_backend='counter')
                self.assertEqual(first[:2],second[:2])
                sig=lambda x:[(r['candidate'],r['makespan'],r['added_copy_bytes']) for r in x[2]['evaluations']]
                self.assertEqual(sig(first),sig(second))
                self.assertEqual(second[2]['preparation_reuse_stats']['global_evaluations'],12)
                self.assertEqual(second[2]['official_calls'],12)
                self.assertEqual(second[2]['protected_grain_attempts'],[.5,1.,2.,.25])

if __name__=='__main__':unittest.main()
