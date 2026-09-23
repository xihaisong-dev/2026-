import unittest
from test_q1 import fixture, SETTINGS, WAITS
from q1_experimental import solve_experimental


class GuardedTests(unittest.TestCase):
    def test_prefix_preserved_and_incumbent_kept(self):
        raw = fixture([(u,u+10) for u in range(10)])
        base = ['local_cost','critical','insertion','comm_rank']
        _, _, control = solve_experimental(raw,SETTINGS,WAITS,4,12,1,base)
        _, result, trial = solve_experimental(raw,SETTINGS,WAITS,4,12,1,base+['guarded_joint'])
        fields = lambda rows:[(r['candidate'],r['makespan'],r['added_copy_bytes']) for r in rows]
        self.assertEqual(fields(control['evaluations'][:9]),fields(trial['evaluations'][:9]))
        self.assertEqual(len(trial['evaluations']),12)
        self.assertLessEqual(result['makespan'],trial['protected_prefix_makespan'])

    def test_incompatible_features_rejected(self):
        with self.assertRaisesRegex(ValueError,'incompatible'):
            solve_experimental(fixture([(0,1)]),SETTINGS,WAITS,4,12,0,['guarded_joint','calibrated'])
