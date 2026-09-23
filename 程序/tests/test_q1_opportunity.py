import json, gzip, tempfile, unittest, subprocess, sys
from pathlib import Path
from unittest.mock import patch
from test_q1 import fixture, SETTINGS, WAITS
from q1_experimental import solve_experimental
from q1_ablation import CONFIGS
from q1_io import write_json, sha
from q1_verified_replay import reuse_verified, summary


class OpportunityTests(unittest.TestCase):
    def test_campaign_cli_exposes_verified_replay_input(self):
        proc=subprocess.run([sys.executable,str(Path(__file__).parents[1]/'q1_opportunity_campaign.py'),'--help'],capture_output=True,text=True)
        self.assertEqual(proc.returncode,0)
        self.assertIn('--verified-plan-runs',proc.stdout)

    def test_rejected_probe_preserves_full_original_search(self):
        raw=fixture([(i,i+1) for i in range(24)]+[(40,41),(50,51),(60,61)])
        base=solve_experimental(raw,SETTINGS,WAITS,3,12,0,CONFIGS['component_fast'])
        poor={'node_to_subgraph':{str(o['id']):100 if o['id'] in [40,41] else 99 for o in raw['ops']},'core_schedules':[[99],[100],[]]}
        info=dict(route='memory',gate='fixture',ranked=[dict(candidate='poor',local_prediction=1e20)],selected_compute_lower_bound=0)
        with patch('q1_memory_routes.routed_candidates',return_value=([('poor',poor)],info)):
            actual=solve_experimental(raw,SETTINGS,WAITS,3,12,0,CONFIGS['routes_guarded'])
        self.assertEqual(base[0],actual[0]);self.assertEqual(base[1],actual[1])
        signature=lambda v:[(r['candidate'],r['makespan'],r['added_copy_bytes']) for r in v[2]['evaluations']]
        self.assertEqual(signature(base),signature(actual))
        record=actual[2]['structural_seed_stats']['ledger'][0]
        self.assertEqual(record['status'],'screened_no_predicted_gain')
        self.assertEqual(record['opportunity_comparison']['full_score_calls'],0)
        self.assertEqual(actual[2]['protected_grain_attempts'],[.5,1.,2.,.25])

    def test_verification_reuse_requires_exact_plan_result_and_original_check(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp);data=p/'data';data.mkdir();(data/'config.txt').write_bytes(b'fixed');(data/'case_001.json').write_bytes(b'input')
            root=p/'prior';folder=root/'case_001_2cores_seed0_test';folder.mkdir(parents=True)
            plan=p/'plan.json';plan.write_bytes(b'{"plan":1}')
            (folder/'plan.json').write_bytes(plan.read_bytes())
            result={'makespan':5};(folder/'evaluation.json.gz').write_bytes(gzip.compress(json.dumps(result).encode()))
            checks={k:True for k in ['makespan','data_movement_bytes','per_core_timeline','memory_peak_by_core','step3_by_task']};write_json(folder/'verification.json',checks)
            row=dict(case='case_001',cores=2,seed=0,config='test',verification_passed=True,verification_calls=1,artifacts={f.name:sha(f.read_bytes()) for f in folder.iterdir()})
            s=dict(completed=True,failures=[],config_sha256=sha(b'fixed'),input_sha256={'case_001.json':sha(b'input')},runs=[row]);write_json(root/'summary.json',s)
            with patch('q1_verified_replay.PROCESSED',p):
                summary.cache_clear();self.assertIsNotNone(reuse_verified([str(root)],'case_001',2,plan,result))
                self.assertIsNone(reuse_verified([str(root)],'case_001',2,plan,{'makespan':6}))
                (folder/'verification.json').write_bytes(b'corrupt')
                with self.assertRaises(ValueError):reuse_verified([str(root)],'case_001',2,plan,result)


if __name__=='__main__':unittest.main()
