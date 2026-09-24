import sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import q3_portfolio as a
from q2_evaluator import key

class PortfolioTests(unittest.TestCase):
    def test_root_reserve_and_global_cap(self):
        def ev(raw,p,*args):return dict(makespan=1000-p['tag'],data_movement_bytes={'added_copy_bytes':0})
        def xs(base,f):return [dict(plan={'tag':base['tag']*100+i+f},move={}) for i in range(1,25)],{}
        with patch.object(a,'evaluate',side_effect=ev),patch.object(a,'asap',side_effect=lambda g,p,*args:xs(p,0)),patch.object(a,'cache',side_effect=lambda g,p,*args:xs(p,30)),patch.object(a,'SceneBGraph'),patch.object(a,'audit',return_value={}):
            _,_,_,s=a.solve({},dict(tag=0),{},0,{},'adaptive',24)
        es=s['evaluations'];self.assertEqual(len(es),24)
        self.assertEqual(len({e['plan_sha256'] for e in es}),24)
        self.assertTrue(all(e['parent']==key(dict(tag=0)) for e in es[:16]))
        self.assertEqual(sum(e['family']=='asap' for e in es[:16]),8)
        self.assertEqual(sum(e['family']=='cache' for e in es[:16]),8)

if __name__=='__main__':unittest.main()
