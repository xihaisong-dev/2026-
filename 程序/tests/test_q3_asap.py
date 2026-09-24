import sys, unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import q3_asap as a

class AsapTests(unittest.TestCase):
    def test_root_survives_early_greedy_improvement(self):
        costs = {0:100, 1:90, 8:70}
        def evaluate(raw, p, *args):
            return dict(makespan=costs.get(p['tag'], 99), data_movement_bytes={'added_copy_bytes':0})
        def proposals(g,p,r,*args):
            ids = range(1,13) if p['tag']==0 else range(20,32)
            return [dict(plan={'tag':i},move={}) for i in ids], {}
        with patch.object(a,'evaluate',side_effect=evaluate), patch.object(a,'proposals',side_effect=proposals), patch.object(a,'SceneBGraph'), patch.object(a,'audit',return_value={}):
            p,r,_,s=a.solve({}, {'tag':0}, {}, 0, {}, 'beam', 12)
        self.assertEqual(p['tag'],8)
        self.assertEqual(len(s['evaluations']),12)
        self.assertEqual(len(set(x['plan_sha256'] for x in s['evaluations'])),12)

    def test_empty_legal_menu_keeps_seed(self):
        r=dict(makespan=100,data_movement_bytes={'added_copy_bytes':0})
        with patch.object(a,'evaluate',return_value=r), patch.object(a,'proposals',return_value=([],{})), patch.object(a,'SceneBGraph'), patch.object(a,'audit',return_value={}):
            p,_,_,s=a.solve({}, {'tag':0}, {}, 0, {}, 'beam', 24)
        self.assertEqual(p,{'tag':0})
        self.assertEqual(s['evaluations'],[])

if __name__=='__main__': unittest.main()
