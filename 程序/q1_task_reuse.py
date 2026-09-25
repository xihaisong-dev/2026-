"""Exact per-Task preparation cache; always rebuild global dependency/DDR events.

Generated boundary IDs are part of the key. A seemingly unchanged node set is
not sufficient: another cut may change boundary COPYs and their tie-break IDs.
"""
import copy,hashlib,inspect,json,types
from collections import OrderedDict
from q1_fast_evaluator import evaluator
from q1_io import official

class TaskReuseEvaluator:
    def __init__(self,raw,bandwidth,capacity,cross,same,max_entries=256):
        if max_entries<1:raise ValueError('max_entries must be positive')
        self.raw=copy.deepcopy(raw);self.bandwidth=bandwidth;self.capacity=dict(capacity)
        self.cross=cross;self.same=same;self.limit=max_entries;self.cache=OrderedDict()
        self.hits=self.misses=self.evaluations=0
        mod=official();engine=evaluator();namespace=dict(engine.__globals__)
        self.local_namespace=namespace
        source=inspect.getsource(mod._build_scene_a_tasks)
        before="""        seq = step1_schedule(graph)
        result2 = step2_spill_insertion(graph, seq, capacity=capacity)
        spill_copy_traffic += sum(
            spill['size'] * (1 + int(spill['spill_out_copies_data']))
            for spill in result2['spill_records'])
        ext_graph = _build_extended_graph(graph, result2)
        prepared = prepare_step3_execution(
            ext_graph, capacity=capacity, bandwidth=bandwidth)"""
        if source.count(before)!=1:raise ValueError('Official local preparation changed')
        source=source.replace(before,"        prepared, spill_bytes = cached_local(graph, capacity, bandwidth)\n        spill_copy_traffic += spill_bytes")
        old="    core_by_task = plan_view['core_by_subgraph']"
        source=source.replace(old,"    touched = {tid: set() for tid in plan_view['subgraph_ids']}\n    for tensor_id in tensor_by_id:\n        for op in producers.get(tensor_id, set()) | consumers.get(tensor_id, set()):\n            if op in mapping: touched[mapping[op]].add(tensor_id)\n"+old)
        old="""        touched_tensors = sorted(
            tensor_id for tensor_id in tensor_by_id
            if producers.get(tensor_id, set()) & task_op_ids
            or consumers.get(tensor_id, set()) & task_op_ids)"""
        if source.count(old)!=1:raise ValueError('Official boundary construction changed')
        source=source.replace(old,'        touched_tensors = sorted(touched[task_id])')
        namespace['cached_local']=self.local
        exec(compile(source,'<q1-task-reuse>','exec'),namespace)
        self.engine=types.FunctionType(engine.__code__,namespace,engine.__name__,engine.__defaults__,engine.__closure__)

    def local(self,graph,capacity,bandwidth):
        key=hashlib.sha256(json.dumps([graph,capacity,bandwidth],sort_keys=True,separators=(',',':')).encode()).digest()
        if key in self.cache:
            self.hits+=1;self.cache.move_to_end(key)
            prepared,byte_count=self.cache[key]
            # Pinned official engine only changes top-level metadata and installs
            # a NEW pipe_cursor dictionary. Nested preparation is read-only.
            return dict(prepared),byte_count
        self.misses+=1;n=self.local_namespace
        seq=n['step1_schedule'](graph)
        spill=n['step2_spill_insertion'](graph,seq,capacity=capacity)
        byte_count=sum(s['size']*(1+int(s['spill_out_copies_data'])) for s in spill['spill_records'])
        ext=n['_build_extended_graph'](graph,spill)
        prepared=n['prepare_step3_execution'](ext,capacity=capacity,bandwidth=bandwidth)
        self.cache[key]=(prepared,byte_count)
        if len(self.cache)>self.limit:self.cache.popitem(last=False)
        return dict(prepared),byte_count

    def evaluate(self,plan):
        result=self.engine(self.raw,plan,self.bandwidth,self.capacity,self.cross,self.same)
        self.evaluations+=1
        return result

    def stats(self):return dict(task_hits=self.hits,task_misses=self.misses,global_evaluations=self.evaluations,cache_entries=len(self.cache))
