import unittest,json,sys,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from q1_io import PROCESSED
from q2_evaluator import load
from q2_current import EvaluationContext


class ContextTest(unittest.TestCase):
    def test_identity_and_isolation(self):
        settings,delay,prov=load();raw=json.loads((PROCESSED/'data/case_006.json').read_text())
        a=EvaluationContext(raw,settings,delay,prov)
        changed=dict(settings,bandwidth=settings['bandwidth']+1)
        self.assertNotEqual(a.identity,EvaluationContext(raw,changed,delay,prov).identity)
        self.assertNotEqual(a.identity,EvaluationContext(raw,settings,delay+1,prov).identity)
        other=copy.deepcopy(prov);other['official_sha256']['new_version']='different'
        self.assertNotEqual(a.identity,EvaluationContext(raw,settings,delay,other).identity)
        plan={'node_to_subgraph':{str(o['id']):0 for o in raw['ops'] if o['op'] not in {'COPY_IN','COPY_OUT'}},'core_schedules':[[0],[]]}
        first=a.evaluate(plan);value=first['makespan'];first['makespan']=-1
        second=a.evaluate(plan);self.assertEqual(second['makespan'],value)
        second['makespan']=-2;self.assertEqual(a.evaluate(plan)['makespan'],value)
        self.assertEqual((a.calls,a.hits),(1,2))


if __name__=='__main__':unittest.main()
