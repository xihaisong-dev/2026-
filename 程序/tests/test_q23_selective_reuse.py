import contextlib,json,random,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from q23_selective_reuse import GenerationReuse,SelectivePreparationReuse
from q23_cache_search import run
from q1_io import write_json

RAW={'ops':[{'id':i,'op':'ADD','pipe':'PIPE_V','cycles':500+i} for i in range(6)],'tensors':[{'id':100,'pos':'UB','size':60000}],'edges':[{'source':100,'target':i} for i in range(6)]}
PLAN={'node_to_subgraph':{str(i):i for i in range(6)},'core_schedules':[[0,5],[1],[2],[3],[4]]}

class ReuseTests(unittest.TestCase):
    def test_candidates_rng_and_restore(self):
        from q3_solver import load
        from q2_solver import SceneBGraph
        import q2_solver as mod
        from q1_structural_seeds import GraphModel
        from q2_timed_portfolio import generate
        s,d,c,_=load();g=SceneBGraph(RAW,s,d);m=GraphModel(RAW,s,dict(task_cross_core_wait_cycles=d,task_same_core_wait_cycles=0))
        original=mod.context;traces=[];states=[]
        for enabled in [False,True]:
            rng=random.Random(3);rows=[];best=PLAN
            reuse=GenerationReuse(g)
            with reuse if enabled else contextlib.nullcontext():
                for i in range(80):
                    family=['joint','remap','granularity','order','insert'][i%5]
                    try:
                        plan=generate(family,m,g,best,5,rng,i);rows.append(plan)
                        if i%7==0:best=plan
                    except ValueError as e:rows.append(str(e))
                if enabled:
                    mapping={i:i for i in range(6)};x=mod.context(g,mapping);x[0].clear()
                    self.assertTrue(mod.context(g,mapping)[0])
            self.assertIs(mod.context,original);traces.append(rows);states.append(rng.getstate())
        self.assertEqual(traces[0],traces[1]);self.assertEqual(states[0],states[1])
        self.assertGreater(reuse.stats['order_plan_hits'],0)

    def test_selective_admission_and_no_hit_bypass(self):
        obj=object.__new__(SelectivePreparationReuse)
        from collections import Counter
        obj.stats=Counter();obj.limit=12000
        fn=obj.wrap('stage',lambda x:{'x':[x]})
        for _ in range(3):fn(1)
        self.assertEqual(obj.stats['hits'],1)
        v=fn(1);v['x'].append(4);self.assertEqual(fn(1),{'x':[1]})
        fn2=obj.wrap('cold',lambda x:x)
        for i in range(130):self.assertEqual(fn2(i),i)
        self.assertEqual(obj.stats['cold_disabled'],1);self.assertGreater(obj.stats['bypassed'],0)

    def test_full_official_results_four_arms(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);write_json(p/'raw.json',RAW);write_json(p/'seed.json',PLAN)
            for q in [2,3]:
                traces=[];objectives=[]
                for name,gen,prep in [('base',False,False),('generation',True,False),('preparation',False,True),('both',True,True)]:
                    out=p/f'{q}_{name}'
                    args=dict(problem=q,graph=str(p/'raw.json'),plan=str(p/'seed.json'),output=str(out),mode='on' if prep else 'off',seconds=20,seed=0,max_proposals=24,cache_mib=1,generation_reuse=gen,selective_preparation=prep)
                    r=run(args);self.assertTrue(r['complete']);self.assertFalse(r['error']);self.assertTrue(r['valid'])
                    objectives.append((r['makespan'],r['added']))
                    rows=json.loads((out/'details.json').read_text(encoding='utf-8'))['rows']
                    traces.append([(x.get('plan_sha256'),x['status'],x.get('result_sha256')) for x in rows])
                for trace in traces[1:]:self.assertEqual(trace,traces[0])
                self.assertEqual(len(set(objectives)),1)

if __name__=='__main__':unittest.main()
