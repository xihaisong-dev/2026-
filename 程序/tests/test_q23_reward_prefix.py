import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from q23_reward_prefix import run
from q1_io import write_json

class PortfolioTests(unittest.TestCase):
    def test_full_portfolios_final_original_replay(self):
        raw={'ops':[{'id':i,'op':'ADD','pipe':'PIPE_V','cycles':500+i} for i in range(6)],'tensors':[{'id':100,'pos':'UB','size':60000}],'edges':[{'source':100,'target':i} for i in range(6)]}
        plan={'node_to_subgraph':{str(i):i for i in range(6)},'core_schedules':[[0,5],[1],[2],[3],[4]]}
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);write_json(p/'raw.json',raw);write_json(p/'seed.json',plan)
            for q in [2,3]:
                evaluations=[];traces=[]
                for reuse in [False,True]:
                    out=p/f'{q}_{reuse}'
                    a=dict(policy="reward",problem=q,graph=str(p/'raw.json'),output=str(out),migration=str(p/'seed.json'),seed_plan=str(p/'seed.json'),anchor=None,reuse=True,ordering_prepare=reuse,seconds=30,cores=5,seed=0,max_proposals=40,cache_mib=32)
                    r=run(a)
                    if r['error']:self.fail((out/'error.txt').read_text(encoding='utf-8'))
                    self.assertTrue(r['valid']);self.assertTrue(r['complete'])
                    trace=json.loads((out/'search/search.json').read_text(encoding='utf-8'))['proposals']
                    traces.append([{k:v for k,v in x.items() if k!='seconds'} for x in trace])
                    self.assertTrue(any(x['phase']=='append' for x in trace))
                    rows=json.loads((out/'scored.json').read_text(encoding='utf-8'));evaluations.append({x['plan_sha256']:x['result_sha256'] for x in rows})
                self.assertEqual(traces[0],traces[1])
                common=evaluations[0].keys()&evaluations[1].keys();self.assertTrue(common)
                for h in common:self.assertEqual(evaluations[0][h],evaluations[1][h])


class WeightTests(unittest.TestCase):
    def test_exploration_and_reward_decay(self):
        from q23_reward_prefix import choose,reward
        from collections import Counter
        import random
        prefix=['joint'];cycle=['joint','cache','insert'];counts=Counter(joint=1,cache=1,insert=1);gains=Counter(joint=.01)
        rng=random.Random(8)
        self.assertEqual(choose(0,prefix,cycle,counts,gains,rng)[0],'joint')
        self.assertEqual([choose(i,prefix,cycle,counts,gains,rng)[0] for i in [1,3,5]],cycle)
        _,a=choose(2,prefix,cycle,counts,gains,random.Random(8));counts['joint']=10
        _,b=choose(2,prefix,cycle,counts,gains,random.Random(8))
        self.assertLess(b['joint'],a['joint']);self.assertTrue(all(v>=1 for v in b.values()))
        self.assertEqual(reward((100,100),(101,0)),0)
        self.assertGreater(reward((100,100),(99,200)),reward((100,100),(100,0)))

if __name__=='__main__':unittest.main()
