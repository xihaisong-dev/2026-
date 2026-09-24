"""Scene-B pilot built on Q1-WRITE-r02 structure; no scene-A score reuse."""
from collections import OrderedDict
import copy,hashlib,json,time
from pathlib import Path
from q2_evaluator import evaluate,key
from q2_solver import SceneBGraph,place,order_plan
from q1_structural_seeds import GraphModel,_component_plan
from q1_memory_routes import hybrid_pool
from q2_bottleneck_j import diagnose,pool


def stable(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


class EvaluationContext:
    """Bounded per-context full-plan cache; all candidate slots still cost budget."""
    def __init__(self,raw,settings,delay,provenance):
        self.raw,self.settings,self.delay=raw,settings,delay
        self.identity=stable(dict(problem=2,scene='B',input=stable(raw),settings=settings,delay=delay,
                                  evaluator=provenance['official_sha256'],config=provenance['config_sha256'],
                                  adapter=hashlib.sha256(Path(__file__).with_name('q2_evaluator.py').read_bytes()).hexdigest()))
        self.cache=OrderedDict();self.calls=0;self.hits=0
    def evaluate(self,plan):
        k=(self.identity,key(plan))
        if k in self.cache:
            self.hits+=1;self.cache.move_to_end(k);return copy.deepcopy(self.cache[k])
        self.calls+=1
        result=evaluate(self.raw,plan,self.settings,self.delay)
        self.cache[k]=copy.deepcopy(result)
        while len(self.cache)>2:self.cache.popitem(last=False)
        return result


def structure_candidates(raw,settings,delay,cores):
    """Reuse Q1 structural groups, not its Task waits or local cost observations."""
    g=SceneBGraph(raw,settings,delay)
    m=GraphModel(raw,settings,dict(task_cross_core_wait_cycles=delay,task_same_core_wait_cycles=0))
    out=[('components_pipe',_component_plan(m,cores,'pipe',True)),
         ('components_reuse',_component_plan(m,cores,'pipe',False,'reuse'))]
    # Q1 hybrid_pool supplies grouping only; discard its A mapping/order entirely.
    partitions=[(name,{int(u):s for u,s in p['node_to_subgraph'].items()}) for name,p in hybrid_pool(m,cores)]
    partitions.extend((name,{u:i for i,group in enumerate(groups) for u in group}) for name,groups in [
        ('chains',m.chain_groups()),('depth8',m.connected_groups({u:m.depth[u]//8 for u in m.ids}))])
    for name,mapping in partitions:
        owners=place(g,mapping,cores,True)
        out.append((name,order_plan(g,mapping,owners,cores,False)))
    # Keep the menu at six slots even if Q1 de-duplicated equal hybrid partitions.
    while len(out)<6:out.append(('structure_padding',copy.deepcopy(out[-1][1])))
    return g,out[:6]


def solve(raw,settings,delay,provenance,cores,migration,mode='guided'):
    if mode not in ['base','ordinary','guided']:raise ValueError(mode)
    start=time.perf_counter();ctx=EvaluationContext(raw,settings,delay,provenance)
    whole={'node_to_subgraph':{str(o['id']):0 for o in raw['ops'] if o['op'] not in {'COPY_IN','COPY_OUT'}},'core_schedules':[[0]]+[[] for _ in range(cores-1)]}
    best=best_r=None;rows=[];diagnostic=None
    def assess(name,p):
        nonlocal best,best_r
        t=time.perf_counter();before=(ctx.calls,ctx.hits)
        try:
            r=ctx.evaluate(p);accepted=best_r is None or (r['makespan'],r['data_movement_bytes']['added_copy_bytes'])<(best_r['makespan'],best_r['data_movement_bytes']['added_copy_bytes'])
            if accepted:best,best_r=copy.deepcopy(p),r
            row=dict(name=name,status='ok',makespan=r['makespan'],bytes=r['data_movement_bytes']['added_copy_bytes'],accepted=accepted)
        except (ValueError,RuntimeError) as e:row=dict(name=name,status='invalid',error=str(e))
        row.update(plan_sha256=key(p),seconds=time.perf_counter()-t,cache_hit=ctx.hits>before[1]);rows.append(row)
    assess('migration_Q1_r02_replayed_B',migration if migration is not None else whole)
    assess('whole_legal_fallback',whole)
    g,candidates=structure_candidates(raw,settings,delay,cores)
    for name,p in candidates:assess(name,p)
    if best is None:raise RuntimeError('No legal baseline')
    base_plan=copy.deepcopy(best);base_result=best_r
    base_seconds=time.perf_counter()-start
    if mode!='base':
        diagnostic=diagnose(raw,best,best_r,settings,delay) if mode=='guided' else None
        proposals=pool(g,best,diagnostic,budget=4)
        for i in range(4):
            if i<len(proposals):item=proposals[i];p=item['plan'];name='J_'+json.dumps(item['move'],sort_keys=True)
            else:p=base_plan;name='J_padding_anchor'
            assess(name,p)
    solve_seconds=time.perf_counter()-start
    # Independent original B replay, with no cache reuse.
    replay_start=time.perf_counter();checked=evaluate(raw,best,settings,delay)
    assert checked==best_r
    stats=dict(mode=mode,context_identity=ctx.identity,slots=len(rows),official_calls=ctx.calls,cache_hits=ctx.hits,
               solve_seconds=solve_seconds,base_seconds=base_seconds,replay_seconds=time.perf_counter()-replay_start,
               diagnostic_seconds=diagnostic['seconds'] if diagnostic else 0,final_replay_equal=True,
               evaluations=rows,base_makespan=base_result['makespan'],base_bytes=base_result['data_movement_bytes']['added_copy_bytes'],
               base_plan_sha256=key(base_plan),diagnosis=diagnostic)
    return best,best_r,stats
