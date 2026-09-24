import copy
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from q3_solver import load,evaluate,audit_cache,solve
from q2_evaluator import evaluate as evaluate_b
from q1_io import PROCESSED,ROOT


class CacheTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.settings,cls.delay,cls.cache,_=load()

    def shared(self):
        raw={'ops':[{'id':i,'op':'ADD','pipe':'PIPE_V','cycles':500} for i in (0,1)],
             'tensors':[{'id':100,'pos':'UB','size':60000}],
             'edges':[{'source':100,'target':i} for i in (0,1)]}
        return raw,{'node_to_subgraph':{'0':0,'1':1},'core_schedules':[[0],[1]]}

    def test_concurrent_cold_misses_not_merged(self):
        raw,p=self.shared();r=evaluate(raw,p,self.settings,self.delay,self.cache)
        self.assertEqual(r['cache_stats']['copy_in_misses'],2)
        self.assertEqual(r['cache_stats']['copy_in_hits'],0)
        self.assertEqual(len([e for e in r['cache_events'] if e['event']=='insert']),1)
        audit_cache(r)

    def test_zero_capacity_and_oversize_bypass(self):
        raw,p=self.shared();b=evaluate_b(raw,p,self.settings,self.delay)
        for cap in [0,59999]:
            c=dict(self.cache,cache_capacity_bytes=cap)
            r=evaluate(raw,p,self.settings,self.delay,c)
            self.assertEqual(b['makespan'],r['makespan'])
            self.assertEqual(b['data_movement_bytes'],r['data_movement_bytes'])
            self.assertEqual(r['cache_final_entries'],[])

    def test_real_hit_traffic_and_replay(self):
        raw=json.loads((PROCESSED/'data/case_005.json').read_text(encoding='utf-8-sig'))
        p=json.loads((ROOT/'图表/runs/20260924-A-q2-delivery-r07/solutions/3cores/case_005_multicore_res.json').read_text(encoding='utf-8-sig'))
        a,r,anchor,s=solve(raw,p,self.settings,self.delay,self.cache,2)
        b,t,_,_=solve(raw,p,self.settings,self.delay,self.cache,2)
        self.assertEqual(a,b);self.assertEqual(r,t)
        self.assertGreater(anchor['cache_stats']['hit_bytes'],0)
        self.assertLessEqual(r['makespan'],anchor['makespan'])
        zero=evaluate(raw,p,self.settings,self.delay,dict(self.cache,cache_capacity_bytes=0))
        baseline=evaluate_b(raw,p,self.settings,self.delay)
        self.assertEqual(zero['makespan'],baseline['makespan'])
        self.assertEqual(anchor['data_movement_bytes'],baseline['data_movement_bytes'])
        bad=copy.deepcopy(r);bad['cache_stats']['hit_bytes']+=1
        with self.assertRaises(AssertionError):audit_cache(bad)


if __name__=='__main__':unittest.main()
