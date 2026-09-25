"""Process-local exact preparation memoization; never cache global simulations.

Full ordered inputs and hardware settings form keys. Deep copies prevent official
simulation cursors/metadata mutating cached payloads. Context restores all symbols.
"""
import copy,hashlib,importlib,json,pickle,time
from collections import OrderedDict,Counter

class PreparationReuse:
    def __init__(self,problem,max_bytes=32*1024*1024):
        self.module=importlib.import_module('multicore_cut_evaluate_problem_'+str(problem))
        self.limit=max_bytes;self.entries=OrderedDict();self.size=0;self.stats=Counter();self.original={}
    def wrap(self,name,fn):
        def call(*args,**kwargs):
            started=time.perf_counter()
            # Preserve insertion/list order; official tie breaking may depend on it.
            key=(name,hashlib.sha256(pickle.dumps((args,kwargs),protocol=5)).digest())
            self.stats['calls']+=1
            if key in self.entries:
                self.stats['hits']+=1;value,size=self.entries.pop(key);self.entries[key]=(value,size)
                out=copy.deepcopy(value);self.stats['hit_seconds']+=time.perf_counter()-started;return out
            self.stats['misses']+=1;value=fn(*args,**kwargs);saved=copy.deepcopy(value)
            size=len(pickle.dumps(saved,protocol=5))
            if size<=self.limit:
                while self.entries and self.size+size>self.limit:
                    _,(_,n)=self.entries.popitem(last=False);self.size-=n;self.stats['evictions']+=1
                self.entries[key]=(saved,size);self.size+=size
            self.stats['miss_seconds']+=time.perf_counter()-started;return value
        return call
    def __enter__(self):
        for n in ['step1_schedule','step2_spill_insertion','prepare_step3_execution']:
            self.original[n]=getattr(self.module,n);setattr(self.module,n,self.wrap(n,self.original[n]))
        return self
    def __exit__(self,*exc):
        for n,fn in self.original.items():setattr(self.module,n,fn)
        self.entries.clear();self.size=0
