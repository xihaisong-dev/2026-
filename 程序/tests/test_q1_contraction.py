import random, unittest
from q1_solver import topological, Graph, greedy_partition, multilevel
from q1_contraction import can_contract, contract
from test_q1 import fixture, SETTINGS, WAITS


class ContractionTests(unittest.TestCase):
    def test_repeated_contractions_equal_full_quotient_check(self):
        rng=random.Random(91)
        for _ in range(80):
            pred={u:set() for u in range(12)};succ={u:set() for u in pred}
            for a in pred:
                for b in pred:
                    if a<b and rng.random()<.24:succ[a].add(b);pred[b].add(a)
            for _ in range(8):
                if len(pred)<2:break
                a,b=rng.sample(sorted(pred),2)
                new_p={u:set() for u in pred if u!=b};new_s={u:set() for u in new_p}
                for u in pred:
                    for v in succ[u]:
                        x,y=(a if u==b else u),(a if v==b else v)
                        if x!=y:new_p[y].add(x);new_s[x].add(y)
                try:topological(new_p,new_s);expected=True
                except ValueError:expected=False
                self.assertEqual(can_contract(pred,succ,a,b),expected)
                if expected:
                    contract(pred,succ,a,b)
                    self.assertEqual(pred,new_p);self.assertEqual(succ,new_s)

    def test_same_hierarchy_and_result(self):
        rng=random.Random(21)
        for _ in range(12):
            edges=[(a,b) for a in range(25) for b in range(a+1,25) if rng.random()<.12]
            raw=fixture(edges);g=Graph(raw,SETTINGS,WAITS)
            initial=greedy_partition(g,3,block_size=2)
            old=multilevel(g,initial,3)
            g.fast_contractions=True
            self.assertEqual(old,multilevel(g,initial,3))


if __name__=='__main__':unittest.main()
