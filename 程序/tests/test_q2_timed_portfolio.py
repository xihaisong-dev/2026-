import gzip,json,random,sys,tempfile,time,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_q1 import fixture
from q1_io import write_json
from q1_structural_seeds import GraphModel,_component_plan
from q2_solver import SceneBGraph
from q2_evaluator import load,evaluate
from q2_timed_portfolio import generate,run,family_weights,objective


class TimedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.settings,cls.delay,_=load()

    def test_candidates_preserve_operators_and_official_scene(self):
        raw=fixture([(0,1),(0,2),(1,3),(2,3),(3,4),(2,5)])
        m=GraphModel(raw,self.settings,dict(task_cross_core_wait_cycles=self.delay,task_same_core_wait_cycles=0))
        g=SceneBGraph(raw,self.settings,self.delay)
        plan=_component_plan(m,5,'pipe',True)
        for family in family_weights(m):
            for step in range(3):
                p=generate(family,m,g,plan,5,random.Random(42),step)
                self.assertEqual(set(map(int,p['node_to_subgraph'])),set(g.ops))
                self.assertEqual(len(p['core_schedules']),5)
                result=evaluate(raw,p,self.settings,self.delay)
                self.assertEqual(result['scene'],'B')

    def test_deadline_failure_does_not_fabricate_solution(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);write_json(root/'graph.json',fixture([(0,1)]))
            s=run(root/'graph.json',root/'out',seconds=.001)
            self.assertEqual(s['status'],'no_verified_solution')
            self.assertFalse((root/'out/verified.json').exists())
            self.assertLess(s['seconds'],5)

    def test_cold_checkpoint_is_original_replay(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);raw=fixture([(0,1),(0,2),(1,3),(2,3)])
            write_json(root/'graph.json',raw)
            s=run(root/'graph.json',root/'out',seconds=15,max_proposals=5)
            self.assertEqual(s['status'],'ok');self.assertFalse(s['worker_error'])
            p=json.loads((root/'out'/s['plan']).read_text())
            with gzip.open(root/'out'/s['evaluation'],'rt',encoding='utf-8') as f:r=json.load(f)
            self.assertEqual(json.loads(json.dumps(evaluate(raw,p,self.settings,self.delay))),r)
            self.assertEqual(objective(r),(s['makespan'],s['added_copy_bytes']))


if __name__=='__main__':unittest.main()
