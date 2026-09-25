import json,tempfile,unittest
from pathlib import Path
from test_q1 import fixture
from q1_full_staged import report
from q1_io import write_json

class FullReportTests(unittest.TestCase):
    def test_mean_of_ratios_and_partial_coverage(self):
        with tempfile.TemporaryDirectory() as name:
            out=Path(name);(out/'rows').mkdir()
            jobs=[dict(case=i,cores=5,method='full') for i in range(1,101)]
            write_json(out/'contract.json',dict(jobs=jobs,methods=['full'],cores=[5],expected=100))
            for i,t1,tk in [(1,100,50),(2,200,200)]:
                write_json(out/'rows'/f'{i}.json',dict(case=i,cores=5,method='full',valid=True,
                    speedup=t1/tk,makespan=tk,added_copy_bytes=0,baseline_makespan=tk,solver_wall_seconds=20))
            s=report(out);self.assertEqual(s['methods']['full'][0]['mean_speedup'],1.5)
            self.assertFalse(s['complete']);self.assertFalse(s['methods']['full'][0]['complete'])
            self.assertEqual(len(json.loads((out/'pending.json').read_text())),98)

    def test_duplicate_jobs_are_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            out=Path(name);(out/'rows').mkdir();j=dict(case=1,cores=5,method='full',valid=False)
            write_json(out/'contract.json',dict(jobs=[j],methods=['full'],cores=[5],expected=1))
            for n in ['a','b']:write_json(out/'rows'/f'{n}.json',j)
            with self.assertRaises(AssertionError):report(out)

if __name__=='__main__':unittest.main()
