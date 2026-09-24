import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from q2_evaluator import load
from q2_bottleneck_j import analyze


class BottleneckTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):load()

    def example(self,dependent=False):
        def op(i,cycles):return dict(id=i,op='ADD',pipe='PIPE_V',cycles=cycles)
        tasks={0:dict(op_by_id={1:op(1,1),2:op(2,1)},op_preds={1:set(),2:{1} if dependent else set()},
                      pipe_ops={'PIPE_V':[1,2]},in_tids={},out_tids={},tensor_by_id={}),
               1:dict(op_by_id={3:op(3,10)},op_preds={3:set()},pipe_ops={'PIPE_V':[3]},in_tids={},out_tids={},tensor_by_id={})}
        links=[dict(source_core=1,source_copy_out_id=3,target_core=0,target_copy_in_id=1)]
        def entry(i,s,e,g):return dict(op_id=i,start=s,end=e,duration=e-s,subgraph_id=g)
        result=dict(makespan=12,per_core_timeline=[dict(core_id=0,ops=[entry(1,10,11,0),entry(2,11,12,1)]),dict(core_id=1,ops=[entry(3,0,10,2)])])
        return analyze(tasks,links,result,0,60)

    def test_ready_follower_is_blocked(self):
        d=self.example();self.assertEqual(d['start_reconstruction_max_error'],0)
        self.assertEqual(len(d['hol']),1);self.assertEqual(d['hol'][0]['opportunity_cycles'],10)
        self.assertEqual(sum(x['end']-x['start']+x['incoming_lag'] for x in d['critical_chain']),12)

    def test_dependent_follower_is_not_hol(self):
        self.assertEqual(self.example(True)['hol'],[])


if __name__=='__main__':unittest.main()
