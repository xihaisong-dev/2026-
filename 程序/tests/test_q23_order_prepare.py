import sys,unittest,random
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from q23_order_prepare import OrderingPreparation
from q23_selective_reuse import GenerationReuse

class OrderTests(unittest.TestCase):
    def test_equivalence_and_state_isolation(self):
        import q2_solver as m
        from q3_solver import load
        s,d,_,_=load()
        raw={'ops':[{'id':i,'op':'ADD','pipe':'PIPE_V','cycles':500+i} for i in range(8)],'tensors':[{'id':100,'pos':'UB','size':60000}],'edges':[{'source':100,'target':i} for i in range(8)]+[{'source':0,'target':7,'data_size':1024}]}
        g=m.SceneBGraph(raw,s,d);original=m.order_plan;traces=[]
        for cls in [GenerationReuse,OrderingPreparation]:
            rows=[];rng=random.Random(3)
            with cls(g) as cache:
                for i in range(40):
                    mapping={j:j if i%3 else j//2 for j in range(8)}
                    owners={v:(v+i)%5 for v in mapping.values()}
                    priority={v:rng.random() for v in owners} if i%2 else None
                    x=m.order_plan(g,mapping,owners,5,i%4!=0,1+i%7,[0,.5,1,2][i%4],priority)
                    rows.append(x)
                    # Returned plans must not expose cached structure.
                    if i==0:
                        x['node_to_subgraph']['0']=999
                        y=m.order_plan(g,mapping,owners,5,i%4!=0,1+i%7,0,priority)
                        self.assertNotEqual(y['node_to_subgraph']['0'],999)
            self.assertIs(m.order_plan,original);traces.append(rows)
        self.assertEqual(traces[0],traces[1]);self.assertGreater(cache.stats['hits'],0)

if __name__=='__main__':unittest.main()
