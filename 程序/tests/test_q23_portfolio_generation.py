"""Fixed-action equivalence separate from time-adaptive portfolio decisions."""
import contextlib,random,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from q23_selective_reuse import GenerationReuse

class FixedActions(unittest.TestCase):
    def test_all_portfolio_families_and_cache_pool(self):
        from q3_solver import load
        from q2_solver import SceneBGraph
        from q1_structural_seeds import GraphModel
        from q2_timed_portfolio import generate
        from q3_neighborhood import pool
        raw={'ops':[{'id':i,'op':'ADD','pipe':'PIPE_V','cycles':500+i} for i in range(6)],'tensors':[{'id':100,'pos':'UB','size':60000}],'edges':[{'source':100,'target':i} for i in range(6)]}
        plan={'node_to_subgraph':{str(i):i for i in range(6)},'core_schedules':[[0,5],[1],[2],[3],[4]]}
        s,d,c,_=load();g=SceneBGraph(raw,s,d);m=GraphModel(raw,s,dict(task_cross_core_wait_cycles=d,task_same_core_wait_cycles=0))
        traces=[];states=[]
        for enabled in [False,True]:
            rng=random.Random(3);rows=[];reuse=GenerationReuse(g)
            with reuse if enabled else contextlib.nullcontext():
                for i in range(42):
                    family=['joint','remap','granularity','order','insert','frontier','packing'][i%7]
                    try:rows.append(generate(family,m,g,plan,5,rng,i))
                    except ValueError as e:rows.append(str(e))
                rows.append(list(pool(g,plan,None,budget=24)))
            traces.append(rows);states.append(rng.getstate())
        self.assertEqual(traces[0],traces[1]);self.assertEqual(states[0],states[1])
        self.assertGreater(sum(v for k,v in reuse.stats.items() if k.endswith('_hits')),0)

if __name__=='__main__':unittest.main()
