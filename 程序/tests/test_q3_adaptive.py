import sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import q3_adaptive as a
from q2_evaluator import key

class AdaptiveTests(unittest.TestCase):
    def test_rediagnosis_after_batch_and_global_budget(self):
        called=[]
        def evaluate(raw,p,*args):
            return {'makespan':100-p['tag']*10,'data_movement_bytes':{'added_copy_bytes':0}}
        def propose(g,p,r,*args):
            called.append(p['tag'])
            return [dict(plan={'tag':i},move={},family='test') for i in range(p['tag']+1,p['tag']+9)],{'label':'compute'}
        with patch.object(a,'evaluate',side_effect=evaluate),patch.object(a,'proposals',side_effect=propose),patch.object(a,'SceneBGraph'),patch.object(a,'audit',return_value={'checked':True}):
            p,r,anchor,s=a.solve({}, {'tag':0},{},0,{},'iterative',8)
        self.assertEqual(called,[0,4])
        self.assertEqual(p,{'tag':8})
        self.assertEqual(s['rounds'][1]['seed'],key({'tag':4}))
        self.assertEqual(len(s['evaluations']),8)
        self.assertEqual(len({x['plan_sha256'] for x in s['evaluations']}),8)

    def test_observed_chain_decomposition_includes_sync(self):
        r={'makespan':30,'per_core_timeline':[{'core_id':0,'ops':[{'op_id':1,'memory_path':'DDR'},{'op_id':2,'pipe':'PIPE_M'}]}]}
        d={'critical_chain':[{'core':0,'op':1,'start':0,'end':15,'incoming_lag':0},{'core':0,'op':2,'start':20,'end':30,'incoming_lag':5}]}
        c=a.classify(r,d)
        self.assertEqual(c['cycles'],{'ddr':15,'sync':5,'compute':10})
        self.assertEqual(c['label'],'ddr')
        self.assertAlmostEqual(sum(c['shares'].values()),1)

if __name__=='__main__':unittest.main()
