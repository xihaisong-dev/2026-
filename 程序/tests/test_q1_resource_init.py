import unittest
from test_q1 import fixture, SETTINGS, WAITS
from q1_solver import Graph, validate
from q1_resource_init import resource_partition
from q1_experimental import solve_experimental


class ResourceInitialTests(unittest.TestCase):
    def test_bounded_deterministic_acyclic_growth(self):
        raw = fixture([(i,i+12) for i in range(12)]+[(i+12,24) for i in range(12)])
        for k in [2,3,4,5]:
            g=Graph(raw,SETTINGS,WAITS)
            a=resource_partition(g,k,width=4,max_ops=6)
            b=resource_partition(g,k,width=4,max_ops=6)
            self.assertEqual(a,b)
            self.assertEqual(set(a),set(g.ops))
            self.assertLessEqual(max(x['ops'] for x in g.resource_init_stats['blocks']),6)
            self.assertLessEqual(g.resource_init_stats['probes'],4*(len(g.ops)+len(set(a.values()))))
            validate(g,g.schedule(a,k)[0])

    def test_resource_weights_change_granularity(self):
        raw=fixture([(i,i+1) for i in range(19)])
        for o in raw['ops']:o['cycles']=100
        g=Graph(raw,SETTINGS,WAITS);a=resource_partition(g,4)
        raw['ops'][0]['cycles']=100000
        h=Graph(raw,SETTINGS,WAITS);b=resource_partition(h,4)
        self.assertNotEqual(a,b)

    def test_initial_ablation_uses_same_budget_and_baseline(self):
        raw=fixture([(i,i+1) for i in range(8)])
        _,a,sa=solve_experimental(raw,SETTINGS,WAITS,3,3,0,[])
        _,b,sb=solve_experimental(raw,SETTINGS,WAITS,3,3,0,['resource_init'])
        self.assertEqual(sa['official_calls'],sb['official_calls'])
        self.assertEqual(sa['singlecore_makespan'],sb['singlecore_makespan'])
        self.assertEqual(sb['evaluations'][1]['candidate'],'resource_initial')
        self.assertLessEqual(b['makespan'],sb['singlecore_makespan'])
