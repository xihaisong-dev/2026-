import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from q23_order_portfolio import run
from q1_io import write_json

class PortfolioTests(unittest.TestCase):
    def test_full_portfolios_final_original_replay(self):
        raw={'ops':[{'id':i,'op':'ADD','pipe':'PIPE_V','cycles':500+i} for i in range(6)],'tensors':[{'id':100,'pos':'UB','size':60000}],'edges':[{'source':100,'target':i} for i in range(6)]}
        plan={'node_to_subgraph':{str(i):i for i in range(6)},'core_schedules':[[0,5],[1],[2],[3],[4]]}
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);write_json(p/'raw.json',raw);write_json(p/'seed.json',plan)
            for q in [2,3]:
                evaluations=[]
                for reuse in [False,True]:
                    out=p/f'{q}_{reuse}'
                    a=dict(problem=q,graph=str(p/'raw.json'),output=str(out),migration=str(p/'seed.json'),seed_plan=str(p/'seed.json'),anchor=None,reuse=True,ordering_prepare=reuse,seconds=30,cores=5,seed=0,max_proposals=40,cache_mib=32)
                    r=run(a)
                    if r['error']:self.fail((out/'error.txt').read_text(encoding='utf-8'))
                    self.assertTrue(r['valid']);self.assertTrue(r['complete'])
                    rows=json.loads((out/'scored.json').read_text(encoding='utf-8'));evaluations.append({x['plan_sha256']:x['result_sha256'] for x in rows})
                common=evaluations[0].keys()&evaluations[1].keys();self.assertTrue(common)
                for h in common:self.assertEqual(evaluations[0][h],evaluations[1][h])

if __name__=='__main__':unittest.main()
