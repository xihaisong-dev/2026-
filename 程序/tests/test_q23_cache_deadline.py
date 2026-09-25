"""Fault injection for supervisor fallback, separate from official numeric tests."""
import json,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from q23_cache_search import run
from q2_timed_portfolio import atomic

def stalled_fixture(args,deadline):
    # Synthetic checkpoint: tests supervisor behavior, not evaluator correctness.
    p=Path(args['output'])
    atomic(p/'verified.json',{'fixture':'verified-anchor','makespan':123,'added':45})
    (p/'unfinished-final.tmp').write_text('partial result must never be selected')
    time.sleep(30)

class DeadlineTests(unittest.TestCase):
    def test_retains_checkpoint_when_final_worker_stalls(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'run'
            args=dict(problem=2,graph='fixture',plan=None,output=str(p),mode='on',seconds=2,seed=0,max_proposals=1,cache_mib=1)
            with patch('q23_cache_search.worker',stalled_fixture):r=run(args)
            self.assertTrue(r['deadline_stop']);self.assertFalse(r['complete'])
            self.assertTrue(r['valid']);self.assertEqual(r['fixture'],'verified-anchor')
            self.assertEqual(json.loads((p/'verified.json').read_text())['makespan'],123)
            self.assertLess(r['total_seconds'],6)

if __name__=='__main__':unittest.main()
