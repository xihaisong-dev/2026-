import unittest,copy
from test_q1 import fixture,SETTINGS,WAITS,evaluate
from q1_task_reuse import TaskReuseEvaluator

class ReuseTests(unittest.TestCase):
    def engine(self,raw):
        return TaskReuseEvaluator(raw,SETTINGS['bandwidth'],SETTINGS['capacity'],
            WAITS['task_cross_core_wait_cycles'],WAITS['task_same_core_wait_cycles'])

    def test_reorder_and_remap_recompute_global_events(self):
        raw=fixture([(0,1),(2,3),(4,5)])
        p={'node_to_subgraph':{str(i):i//2 for i in range(6)},'core_schedules':[[0,1],[2]]}
        e=self.engine(raw)
        self.assertEqual(e.evaluate(p),evaluate(raw,p))
        q=copy.deepcopy(p);q['core_schedules']=[[2],[1,0]]
        self.assertEqual(e.evaluate(q),evaluate(raw,q));self.assertEqual(e.hits,3)
        self.assertEqual(e.evaluate(p),evaluate(raw,p));self.assertEqual(e.evaluations,3)

    def test_local_split_invalidates_changed_task_only_when_boundary_ids_match(self):
        raw=fixture([(0,1),(2,3),(4,5)])
        p={'node_to_subgraph':{str(i):i//2 for i in range(6)},'core_schedules':[[0,1],[2]]}
        e=self.engine(raw);e.evaluate(p)
        q=copy.deepcopy(p);q['node_to_subgraph']['5']=3;q['core_schedules']=[[0,1],[2,3]]
        self.assertEqual(e.evaluate(q),evaluate(raw,q));self.assertGreater(e.hits,0)
        self.assertGreater(e.misses,3)

    def test_generated_ids_and_changed_tensor_boundary_cannot_false_hit(self):
        raw=fixture([(0,1),(1,2),(1,3),(2,4),(3,4)])
        e=self.engine(raw)
        for mapping in [[0,0,1,2,3],[0,1,2,3,4],[0,0,1,1,2]]:
            p={'node_to_subgraph':{str(i):s for i,s in enumerate(mapping)},'core_schedules':[sorted(set(mapping)),[]]}
            self.assertEqual(e.evaluate(p),evaluate(raw,p))
        self.assertEqual(e.evaluations,3)

if __name__=='__main__':unittest.main()
