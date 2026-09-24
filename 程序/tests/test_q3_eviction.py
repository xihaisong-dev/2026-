import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from q3_eviction import extract

class EvictionTests(unittest.TestCase):
    def test_reinsertion_replaces_old_eviction_witness(self):
        ops=[dict(op_id=i,subgraph_id=i,duration=10) for i in range(1,6)]
        def e(t,kind,tid,op,evicted=None):
            r=dict(time=t,event=kind,tensor_id=tid,core_id=0,op_id=op,size_bytes=8)
            if kind=='insert':r['evicted_tensor_ids']=evicted or []
            return r
        result=dict(per_core_timeline=[dict(core_id=0,ops=ops)],cache_events=[
            e(0,'insert',11,1),e(1,'insert',22,2,[11]),e(2,'miss',11,3),
            e(3,'insert',11,3,[22]),e(4,'insert',33,4,[11]),e(5,'miss',11,5)])
        ws=extract(result,{(0,3),(0,5)})
        ws.sort(key=lambda x:x['read_time'])
        self.assertEqual([x['source_group'] for x in ws],[2,4])
        self.assertEqual([x['fill_time'] for x in ws],[0,3])
        self.assertEqual(len(extract(result,{(0,5)})),1)

if __name__=='__main__':unittest.main()
