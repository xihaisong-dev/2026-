import gzip,json,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from q1_io import write_json
from q2_evaluator import load,evaluate,key
from q2_timed_portfolio import atomic,run
from q2_full_timed import saved_row_valid
from test_q1 import fixture


def checkpoint_then_wait(args,deadline):
    s,d,_=load();raw=json.loads(Path(args['graph']).read_text())
    plan={'node_to_subgraph':{str(o['id']):0 for o in raw['ops'] if o['op'] not in {'COPY_IN','COPY_OUT'}},'core_schedules':[[0],[],[],[],[]]}
    r=evaluate(raw,plan,s,d);folder=Path(args['output'])
    write_json(folder/'plan.json',plan)
    with gzip.open(folder/'evaluation.json.gz','wt',encoding='utf-8') as f:json.dump(r,f)
    atomic(folder/'verified.json',dict(plan='plan.json',evaluation='evaluation.json.gz',makespan=r['makespan'],
        added_copy_bytes=r['data_movement_bytes']['added_copy_bytes'],plan_sha256=key(plan),official_original=True))
    time.sleep(60)


class CampaignTests(unittest.TestCase):
    def test_timeout_keeps_complete_official_checkpoint(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d);raw=fixture([(0,1),(1,2)]);write_json(folder/'input.json',raw)
            with patch('q2_timed_portfolio.worker',checkpoint_then_wait):
                s=run(folder/'input.json',folder/'out',seconds=2)
            self.assertTrue(s['deadline_stop']);self.assertEqual(s['status'],'ok')
            settings,delay,_=load();p=json.loads((folder/'out/plan.json').read_text())
            with gzip.open(folder/'out/evaluation.json.gz','rt',encoding='utf-8') as f:saved=json.load(f)
            self.assertEqual(json.loads(json.dumps(evaluate(raw,p,settings,delay))),saved)
            self.assertLess(s['seconds'],6)

    def test_resume_rejects_corrupted_completed_result(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);folder=root/'jobs/case_001_protected';folder.mkdir(parents=True)
            write_json(folder/'summary.json',dict(plan='plan.json',evaluation='evaluation.gz'))
            write_json(folder/'audit.json',dict(equal=True));write_json(folder/'plan.json',{})
            (folder/'evaluation.gz').write_bytes(b'corrupt')
            self.assertFalse(saved_row_valid(root,dict(case=1,arm='protected',valid=True,
                plan_sha256='wrong',evaluation_sha256='wrong')))


if __name__=='__main__':unittest.main()
