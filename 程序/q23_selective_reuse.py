"""Experimental exact reuse; graph must remain immutable within the context.

Memoizing deterministic inner operations preserves all outer RNG consumption.
No whole proposal or global simulation is memoized.
"""
import hashlib,pickle,time
from collections import Counter,OrderedDict
from q23_preparation_reuse import PreparationReuse

class GenerationReuse:
    def __init__(self,graph,max_bytes=32*1024**2):
        import q2_solver
        self.module=q2_solver;self.graph=graph;self.limit=max_bytes
        self.entries=OrderedDict();self.size=0;self.stats=Counter();self.original={}
    def wrap(self,name,fn):
        def call(g,*args,**kwargs):
            if g is not self.graph:return fn(g,*args,**kwargs)
            t=time.perf_counter();k=(name,hashlib.sha256(pickle.dumps((args,kwargs),protocol=5)).digest())
            self.stats[name+'_calls']+=1
            if k in self.entries:
                self.stats[name+'_hits']+=1;b=self.entries.pop(k);self.entries[k]=b
                value=pickle.loads(b)
            else:
                self.stats[name+'_misses']+=1;value=fn(g,*args,**kwargs);b=pickle.dumps(value,protocol=5)
                if len(b)<=self.limit//4:
                    while self.entries and self.size+len(b)>self.limit:
                        _,old=self.entries.popitem(last=False);self.size-=len(old);self.stats['evictions']+=1
                    self.entries[k]=b;self.size+=len(b)
                else:self.stats['oversize']+=1
            self.stats[name+'_seconds']+=time.perf_counter()-t
            self.stats['peak_payload_bytes']=max(self.stats['peak_payload_bytes'],self.size)
            return value
        return call
    def __enter__(self):
        for n in ['context','order_plan','proxy']:
            self.original[n]=getattr(self.module,n);setattr(self.module,n,self.wrap(n,self.original[n]))
        return self
    def __exit__(self,*exc):
        for n,fn in self.original.items():setattr(self.module,n,fn)
        self.entries.clear();self.size=0

class SelectivePreparationReuse(PreparationReuse):
    """Separate stage budgets, second-use admission, oversized-entry bypass.

    A stage with no hit in 128 probes stops caching for this invocation.
    Hashes include complete ordered inputs and settings. Snapshot hits are isolated.
    """
    def wrap(self,name,fn):
        entries=OrderedDict();history=OrderedDict();size=0;calls=hits=0;disabled=False
        limit=self.limit//3
        def call(*args,**kwargs):
            nonlocal size,calls,hits,disabled
            self.stats['calls']+=1;self.stats[name+'_calls']+=1
            if disabled:
                self.stats['bypassed']+=1;return fn(*args,**kwargs)
            calls+=1;k=hashlib.sha256(pickle.dumps((args,kwargs),protocol=5)).digest()
            if k in entries:
                hits+=1;self.stats['hits']+=1;self.stats[name+'_hits']+=1
                b=entries.pop(k);entries[k]=b;return pickle.loads(b)
            self.stats['misses']+=1;value=fn(*args,**kwargs)
            if k in history:
                history.move_to_end(k);b=pickle.dumps(value,protocol=5)
                if len(b)<=limit//4:
                    while entries and size+len(b)>limit:
                        _,old=entries.popitem(last=False);size-=len(old);self.stats['evictions']+=1
                    entries[k]=b;size+=len(b)
                    self.stats[name+'_peak_payload_bytes']=max(self.stats[name+'_peak_payload_bytes'],size)
                else:self.stats['oversize']+=1
            else:
                history[k]=None;self.stats['first_use_bypass']+=1
                if len(history)>4096:history.popitem(last=False)
            if calls>=128 and hits==0:
                disabled=True;entries.clear();history.clear();size=0;self.stats[name+'_disabled']=1
            return value
        return call
