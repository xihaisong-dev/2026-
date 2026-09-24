import unittest,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from q1_io import PROCESSED
from q2_evaluator import load,key
from q2_structural_route import menu


class RouteTest(unittest.TestCase):
    def test_protected_slots_and_unconditional_weak_fallback(self):
        settings,delay,_=load()
        from stub_multicore_cut_and_schedule import derive_multicore_plan
        from evaluation_validation import validate_task_order
        for i in [12,48,50,22,24,35]:
            raw=json.loads((PROCESSED/f'data/case_{i:03}.json').read_text(encoding='utf-8'))
            for n in [2,5]:
                _,a=menu(raw,settings,delay,n,'legacy');_,b=menu(raw,settings,delay,n,'routed')
                self.assertEqual([key(p) for _,p in a[:4]],[key(p) for _,p in b[:4]])
                if i in [12,22]:self.assertEqual([key(p) for _,p in a],[key(p) for _,p in b])
                for _,p in b:validate_task_order(derive_multicore_plan(raw,p))


if __name__=='__main__':unittest.main()
