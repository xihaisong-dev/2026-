"""Zero-official-evaluation menu equivalence, padding, repeated-call isolation."""
import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from q2_evaluator import load
from q2_overhead_campaign import generate
from q2_reserve_fast import menu as original
from q2_reserve_shared import menu as shared

class SharedPreparationTests(unittest.TestCase):
    def test_menus_and_input_isolation(self):
        settings,delay,_=load()
        for family in ['components','forkjoin','layered','pressure']:
            for n in [1,8,17,33]:
                raw=generate(dict(family=family,n=n,seed=907));before=copy.deepcopy(raw)
                for cores in [2,3,4,5]:
                    whole=dict(node_to_subgraph={str(o['id']):0 for o in raw['ops']},core_schedules=[[0]]+[[] for _ in range(cores-1)])
                    _,a=original(raw,settings,delay,cores,whole,{})
                    _,b=shared(raw,settings,delay,cores,whole,{})
                    _,c=shared(raw,settings,delay,cores,whole,{})
                    self.assertEqual(a,b,(family,n,cores));self.assertEqual(b,c);self.assertEqual(raw,before)

if __name__=='__main__':unittest.main()
