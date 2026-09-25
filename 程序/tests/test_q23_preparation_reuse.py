import sys,copy,unittest,importlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from q3_solver import load,evaluate as q3
from q2_evaluator import evaluate as q2
from q23_preparation_reuse import PreparationReuse,SerializedPreparationReuse

class ReuseTests(unittest.TestCase):
    cache_type=PreparationReuse
    def test_original_equality_changed_order_hardware_and_restore(self):
        s,d,c,_=load()
        raw={'ops':[{'id':i,'op':'ADD','pipe':'PIPE_V','cycles':500+i} for i in range(3)],'tensors':[{'id':100,'pos':'UB','size':60000}],'edges':[{'source':100,'target':i} for i in range(3)]}
        a={'node_to_subgraph':{str(i):i for i in range(3)},'core_schedules':[[0,1],[2],[],[],[]]}
        b=copy.deepcopy(a);b['core_schedules'][0]=[1,0]
        t=copy.deepcopy(s);t['bandwidth']=s['bandwidth']/2
        for problem in [2,3]:
            def ev(p,hw,cache):return q2(raw,p,hw,d) if problem==2 else q3(raw,p,hw,d,cache)
            specs=[(a,s,c),(b,s,c),(a,t,c),(a,s,dict(c,cache_capacity_bytes=0)),(a,s,c)]
            expected=[ev(*x) for x in specs];module=importlib.import_module('multicore_cut_evaluate_problem_'+str(problem));original=module.prepare_step3_execution
            with self.cache_type(problem) as reuse:
                actual=[ev(*x) for x in specs];self.assertEqual(expected,actual);self.assertGreater(reuse.stats['hits'],0)
            self.assertIs(module.prepare_step3_execution,original)
    def test_failure_restores_symbols(self):
        load();m=importlib.import_module('multicore_cut_evaluate_problem_2');fn=m.step1_schedule
        with self.assertRaises(RuntimeError):
            with self.cache_type(2):raise RuntimeError('test')
        self.assertIs(m.step1_schedule,fn)

class SerializedReuseTests(ReuseTests):
    cache_type=SerializedPreparationReuse
    def test_snapshot_isolation_and_refill(self):
        load();cache=SerializedPreparationReuse(2)
        call=cache.wrap('synthetic',lambda x:{'x':[x]})
        a=call(3);a['x'][0]=100
        b=call(3);self.assertEqual(b,{'x':[3]});b['x'].append(4)
        self.assertEqual(call(3),{'x':[3]})
        from q23_preserved_trial import refill
        seed={'id':-1};base=[({'id':i},'base') for i in range(24)]
        extra=[base[0],({'id':100},'extra'),({'id':100},'duplicate')]
        result=refill(base,extra,seed)
        self.assertEqual(result[:16],base[:16]);self.assertEqual(len(result),24)
        self.assertEqual(result[16],extra[1]);self.assertEqual(result[17:],base[16:23])

if __name__=='__main__':unittest.main()
