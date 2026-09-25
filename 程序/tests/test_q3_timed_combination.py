import sys,tempfile,json,gzip,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from q1_io import write_json
from q3_solver import load,evaluate,audit_cache
from q3_timed_combination import run

class TimedL2Tests(unittest.TestCase):
    def test_same_plan_uses_Q3_and_preserves_valid_checkpoint(self):
        raw={'ops':[{'id':i,'op':'ADD','pipe':'PIPE_V','cycles':500} for i in (0,1)],
             'tensors':[{'id':100,'pos':'UB','size':60000}],
             'edges':[{'source':100,'target':i} for i in (0,1)]}
        plan={'node_to_subgraph':{'0':0,'1':1},'core_schedules':[[0],[1],[],[],[]]}
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);write_json(root/'raw.json',raw);write_json(root/'seed.json',plan)
            q=run(root/'raw.json',root/'seed.json',root/'out',seconds=10,max_proposals=8)
            self.assertEqual(q['status'],'ok');self.assertFalse(q['worker_error'])
            selected=json.loads((root/'out'/q['plan']).read_text())
            with gzip.open(root/'out'/q['evaluation'],'rt',encoding='utf-8') as f:r=json.load(f)
            s,delay,c,_=load();actual=evaluate(raw,selected,s,delay,c)
            self.assertEqual(json.loads(json.dumps(actual)),r);audit_cache(actual)
            self.assertLessEqual(r['makespan'],evaluate(raw,plan,s,delay,c)['makespan'])

    def test_timeout_without_verified_result_reports_failure(self):
        with tempfile.TemporaryDirectory() as d:
            q=run('missing.json','missing-seed.json',Path(d)/'out',seconds=.001)
            self.assertEqual(q['status'],'no_verified_solution')

if __name__=='__main__':unittest.main()
