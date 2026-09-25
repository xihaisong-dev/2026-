"""Exact effective-precedence certificate for reusing scene-B candidate scores.

No official module, function, global or input graph is modified. A certificate is
an instance-specific equality check, NOT a universal A/B equivalence assertion.
Returned B results retain their original scene label. The experiment runner must
re-evaluate every selected proxy winner with official A before reporting it.
"""
from __future__ import annotations
import hashlib
import json
import time
from evaluate import config_values, evaluate_plan
from multicore_cut_evaluate_problem_1 import _build_scene_a_tasks
from multicore_cut_evaluate_problem_2 import _build_scene_b_tasks
from schedule_step3 import PIPES, _op_duration, _uses_ddr_bandwidth, op_pipe

CERTIFICATE_VERSION = 'prepared_effective_partial_order_v2'


def _canonical_task(task, original_compute_ids, bandwidth, capacity):
    """Canonical keys are (Pipe, FIFO position), independent of global seq."""
    if task is None:
        return dict(operations=(), predecessors=(), pipe_orders=tuple((p, ()) for p in PIPES),
                    memory_peak=tuple(sorted((p,0) for p in capacity)))
    seq=task['seq']; seq_pos={u:i for i,u in enumerate(seq)}
    if len(seq_pos)!=len(seq) or set(seq_pos)!=set(task['op_by_id']):
        raise ValueError('prepared sequence does not exactly cover operations')
    if seq_pos!=task['seq_pos']: raise ValueError('prepared seq_pos disagrees with seq')
    ordered=[u for p in PIPES for u in task['pipe_ops'][p]]
    pos={u:i for i,u in enumerate(ordered)}
    if len(pos)!=len(ordered) or set(pos)!=set(seq):
        raise ValueError('prepared pipe orders do not exactly cover operations')
    operations=[]; predecessors=[]
    for u in ordered:
        op=task['op_by_id'][u]
        for v in task['op_preds'][u]:
            if u not in task['op_succs'][v]: raise ValueError('prepared pred/succ asymmetry')
        for v in task['op_succs'][u]:
            if u not in task['op_preds'][v]: raise ValueError('prepared succ/pred asymmetry')
        operations.append((u if u in original_compute_ids else None,op['op'],op_pipe(op),
            _op_duration(op,task['in_tids'],task['out_tids'],task['tensor_by_id'],bandwidth),
            bool(_uses_ddr_bandwidth(op,task['in_tids'],task['out_tids'],task['tensor_by_id']))))
        predecessors.append(tuple(sorted(pos[v] for v in task['op_preds'][u])))
    return dict(operations=tuple(operations), predecessors=tuple(predecessors),
                pipe_orders=tuple((p,tuple(pos[u] for u in task['pipe_ops'][p])) for p in PIPES),
                memory_peak=tuple(sorted(task['step3']['memory_peak'].items())))


def _effective_predecessors(signature):
    """Remove only edges explicitly implied by each fixed Pipe FIFO chain.

    For a target, all predecessors on the same source Pipe are dominated by the
    latest one. Same-Pipe predecessors earlier than the target are dominated by
    its immediate FIFO predecessor. A same-Pipe self/back edge is rejected.
    """
    locations={u:(pi,j) for pi,(_,order) in enumerate(signature['pipe_orders']) for j,u in enumerate(order)}
    out=[]
    for u,preds in enumerate(signature['predecessors']):
        target_pipe,target_rank=locations[u]; last_by_pipe={}
        for v in preds:
            source_pipe,source_rank=locations[v]
            if source_pipe==target_pipe:
                if source_rank>=target_rank: raise ValueError('backward/self same-Pipe dependency')
                continue
            old=last_by_pipe.get(source_pipe)
            if old is None or locations[old][1]<source_rank:last_by_pipe[source_pipe]=v
        effective=set(last_by_pipe.values())
        if target_rank:effective.add(signature['pipe_orders'][target_pipe][1][target_rank-1])
        out.append(tuple(sorted(effective)))
    return tuple(out)


def _reachability(predecessors):
    """Exact DAG transitive closure using Python integer bitsets."""
    from collections import deque
    size=len(predecessors);succ=[[] for _ in range(size)];degree=list(map(len,predecessors))
    for v,preds in enumerate(predecessors):
        for u in preds:succ[u].append(v)
    ready=deque(i for i,d in enumerate(degree) if not d);topo=[]
    while ready:
        u=ready.popleft();topo.append(u)
        for v in succ[u]:
            degree[v]-=1
            if not degree[v]:ready.append(v)
    if len(topo)!=size:raise ValueError('effective execution dependencies contain a cycle')
    reach=[0]*size
    for u in reversed(topo):
        mask=0
        for v in succ[u]:mask|=(1<<v)|reach[v]
        reach[u]=mask
    return reach


def _compare_effective_states(a,b):
    """Check full descriptors, then exact equality of effective partial orders."""
    for section in ('operations','pipe_orders','memory_peak'):
        if a[section]!=b[section]:return dict(equivalent=False,reason=section+'_mismatch')
    pa,pb=_effective_predecessors(a),_effective_predecessors(b)
    evidence=dict(a_effective_sha256=_signature_hash(pa),b_effective_sha256=_signature_hash(pb))
    if pa==pb:
        evidence.update(equivalent=True,proof_method='fifo_dominance_exact_equality',verified_difference_edges=0)
        return evidence
    edges_a={(u,v) for v,ps in enumerate(pa) for u in ps}
    edges_b={(u,v) for v,ps in enumerate(pb) for u in ps}
    only_a,only_b=edges_a-edges_b,edges_b-edges_a
    rb=_reachability(pb)
    for u,v in sorted(only_a):
        if not (rb[u]>>v)&1:
            evidence.update(equivalent=False,reason='a_edge_not_implied_by_b',unreachable_edge=(u,v));return evidence
    del rb
    ra=_reachability(pa)
    for u,v in sorted(only_b):
        if not (ra[u]>>v)&1:
            evidence.update(equivalent=False,reason='b_edge_not_implied_by_a',unreachable_edge=(u,v));return evidence
    evidence.update(equivalent=True,proof_method='bidirectional_exact_reachability',
                    a_difference_edges=len(only_a),b_difference_edges=len(only_b),
                    verified_difference_edges=len(only_a)+len(only_b))
    return evidence


def _signature_hash(signature):
    return hashlib.sha256(json.dumps(signature,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def certify_equivalence(graph, plan, config_path=None):
    """Build official prepared graphs and certify their effective partial orders.

    Returns a JSON-serializable audit certificate. It does not run either global
    multicore simulator. A failed certificate merely requests the A fallback.
    Descriptors are compared directly and differing effective edges are proved
    redundant by exact reachability; hashes serve only audit identification.
    """
    started=time.perf_counter()
    meta=dict(certificate_version=CERTIFICATE_VERSION,certificate_passed=False,
              score_source=None,reason=None,per_core=[])
    def finish(reason):
        meta['reason']=reason
        evidence=dict(version=meta['certificate_version'],passed=meta['certificate_passed'],
                      reason=reason,per_core=meta['per_core'],
                      traffic=meta.get('certified_data_movement_bytes'))
        meta['certificate_sha256']=_signature_hash(evidence)
        meta['certification_seconds']=time.perf_counter()-started
        return meta
    schedules=plan.get('core_schedules',[])
    if not schedules or any(len(s)>1 for s in schedules):
        return finish('not_at_most_one_subgraph_per_core')
    base,_,_,_=config_values(config_path)
    try:
        ta=time.perf_counter()
        tasks_a,cross_a,traffic_a,view_a=_build_scene_a_tasks(graph,plan,**base)
        meta['prepare_a_seconds']=time.perf_counter()-ta
        if any(task['pred_tasks'] for task in tasks_a.values()):
            return finish('scene_a_has_task_dependencies')
        tb=time.perf_counter()
        tasks_b,cross_links,cross_b,traffic_b,view_b=_build_scene_b_tasks(graph,plan,**base)
        meta['prepare_b_seconds']=time.perf_counter()-tb
        if cross_links or cross_a or cross_b:
            return finish('cross_task_or_cross_core_communication_present')
        if view_a['num_cores']!=view_b['num_cores'] or view_a['num_cores']!=len(schedules):
            return finish('core_count_mismatch')
        if traffic_a!=traffic_b:
            return finish('data_movement_dictionary_mismatch')
        a_by_core={}
        for task in tasks_a.values():
            c=task['core_id']
            if c in a_by_core:return finish('multiple_scene_a_tasks_on_one_core')
            a_by_core[c]=task
        eligible={o['id'] for o in graph['ops'] if o['op'] not in {'COPY_IN','COPY_OUT'}}
        for c in range(len(schedules)):
            task_a=a_by_core.get(c)
            task_b=tasks_b[c]
            if task_b['core_id']!=c:return finish('prepared_core_identity_mismatch')
            sig_a=_canonical_task(task_a,eligible,base['bandwidth'],base['capacity'])
            sig_b=_canonical_task(task_b,eligible,base['bandwidth'],base['capacity'])
            entry=dict(core_id=c,operations=len(sig_a['operations']),
                       a_sha256=_signature_hash(sig_a),b_sha256=_signature_hash(sig_b))
            # Full descriptors and effective partial orders are checked directly;
            # hashes are audit identifiers, never a substitute for checking.
            entry['raw_exact_equal']=(sig_a==sig_b)
            entry.update(_compare_effective_states(sig_a,sig_b))
            meta['per_core'].append(entry)
            if not entry['equivalent']:
                return finish('prepared_effective_partial_order_mismatch')
        meta['certificate_passed']=True
        meta['score_source']='official_B_after_exact_prepared_equivalence'
        meta['certified_data_movement_bytes']=traffic_a
        return finish('certified_effective_partial_order_equivalence')
    except Exception as error:
        # If only B preparation is unsuitable, A may still be valid. The caller
        # deliberately sends every failure through the unchanged A evaluator.
        meta['certificate_error']=type(error).__name__+': '+str(error)
        return finish('official_preparation_or_certificate_check_failed')


def evaluate_a_candidate(graph, plan, config_path=None):
    """Return `(unchanged official result, certificate/provenance metadata)`.

    On pass only the candidate score may be reused. The final selected plan must
    still be evaluated using official A and checked against the certified score.
    On any failed condition the complete official A evaluator is called here.
    """
    meta=certify_equivalence(graph,plan,config_path)
    ts=time.perf_counter()
    if meta['certificate_passed']:
        result=evaluate_plan(graph,plan,2,config_path)
        if result['data_movement_bytes']!=meta['certified_data_movement_bytes']:
            raise AssertionError('B simulator traffic differs from certified preparation')
        meta['score_source_problem']=2
    else:
        result=evaluate_plan(graph,plan,1,config_path)
        meta['score_source']='official_A_fallback'
        meta['score_source_problem']=1
    meta['simulation_seconds']=time.perf_counter()-ts
    meta['total_seconds']=meta['certification_seconds']+meta['simulation_seconds']
    return result,meta
