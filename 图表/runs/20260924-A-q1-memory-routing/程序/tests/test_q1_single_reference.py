import copy
import unittest
from test_q1 import fixture, SETTINGS, WAITS, evaluate
from singlecore_evaluate import evaluate_singlecore,build_singlecore_plan
from q1_single_reference import reference,reuse


class SingleReferenceTests(unittest.TestCase):
    def test_exact_official_equivalence_with_idle_cores(self):
        for edges in [[(0,1),(0,2),(1,3),(2,3)],[(i,i+8) for i in range(8)]]:
            raw=fixture(edges)
            result=evaluate_singlecore(raw,60,SETTINGS['capacity'],1000,100)
            record=reference(raw,SETTINGS,WAITS,result)
            for cores in [2,3,4,5]:
                plan=build_singlecore_plan(raw);plan['core_schedules'] += [[] for _ in range(cores-1)]
                self.assertEqual(reuse(record,raw,SETTINGS,WAITS,cores),evaluate(raw,plan))
            bad=copy.deepcopy(raw);bad['ops'][0]['cycles']+=1
            with self.assertRaises(ValueError):reuse(record,bad,SETTINGS,WAITS,2)
            record['result']['makespan']+=1
            with self.assertRaises(ValueError):reuse(record,raw,SETTINGS,WAITS,2)

    def test_search_trajectory_preserved(self):
        from q1_experimental import solve_experimental
        from q1_ablation import CONFIGS
        raw=fixture([(i,i+8) for i in range(8)])
        ref=reference(raw,SETTINGS,WAITS,evaluate_singlecore(raw,60,SETTINGS['capacity'],1000,100))
        for config in ['shared_region','shared_resource']:
            a,b,c=solve_experimental(raw,SETTINGS,WAITS,3,12,0,CONFIGS[config])
            d,e,f=solve_experimental(raw,SETTINGS,WAITS,3,12,0,CONFIGS[config],single_reference=ref)
            self.assertEqual((a,b),(d,e))
            self.assertEqual([(x['candidate'],x['makespan']) for x in c['evaluations']],
                             [(x['candidate'],x['makespan']) for x in f['evaluations']])
            self.assertEqual(c['official_calls'],f['official_calls']+1)
