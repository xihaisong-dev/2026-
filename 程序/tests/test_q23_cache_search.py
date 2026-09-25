import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from q23_cache_search import run
from q1_io import write_json

class CacheSearchTests(unittest.TestCase):
    def test_identical_candidate_prefix_and_original_final_replay(self):
        raw={'ops':[{'id':i,'op':'ADD','pipe':'PIPE_V','cycles':500+i} for i in range(3)],'tensors':[{'id':100,'pos':'UB','size':60000}],'edges':[{'source':100,'target':i} for i in range(3)]}
        plan={'node_to_subgraph':{str(i):i for i in range(3)},'core_schedules':[[0],[1],[2],[],[]]}
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder);write_json(p/'raw.json',raw);write_json(p/'seed.json',plan)
            for q in [2,3]:
                results=[];traces=[]
                for mode in ['off','on']:
                    out=p/f'{q}_{mode}';args=dict(problem=q,graph=str(p/'raw.json'),plan=str(p/'seed.json'),output=str(out),mode=mode,seconds=15,seed=0,max_proposals=8,cache_mib=1)
                    r=run(args);self.assertTrue(r['complete']);self.assertFalse(r['error']);self.assertTrue(r['valid']);results.append((r['makespan'],r['added']))
                    d=json.loads((out/'details.json').read_text());traces.append([(v.get('plan_sha256'),v['status'],v.get('result_sha256')) for v in d['rows']])
                self.assertEqual(results[0],results[1]);self.assertEqual(traces[0],traces[1])
    def test_hard_deadline_without_checkpoint_is_failure(self):
        with tempfile.TemporaryDirectory() as d:
            r=run(dict(problem=2,graph='missing',plan=None,output=str(Path(d)/'run'),mode='on',seconds=.001,seed=0,max_proposals=96,cache_mib=1))
            self.assertFalse(r['valid']);self.assertTrue(r['deadline_stop'])

if __name__=='__main__':unittest.main()
