"""Q2-seeded deterministic cache-event neighborhood search; official Q3 scoring."""
import copy
import importlib
import time
from collections import Counter, OrderedDict
from q1_io import PROCESSED
from q2_evaluator import check, key, load as load_b
from q2_solver import SceneBGraph
from q3_neighborhood import pool
from q2_physical import PhysicalScorer


def load():
    settings, delay, provenance = load_b()
    module = importlib.import_module('multicore_cut_evaluate_problem_3')
    cache = module.read_cache_config(str(PROCESSED / 'data/config.txt'))
    return settings, delay, cache, provenance


def evaluate(raw, plan, settings, delay, cache):
    from multicore_cut_evaluate_problem_3 import evaluate_problem_3
    r = evaluate_problem_3(raw, plan, settings['bandwidth'], settings['capacity'], delay,
                          cache['cache_capacity_bytes'], cache['cache_bandwidth_bytes_per_cycle'])
    check(r, settings, delay)
    return r


def audit_cache(r):
    """Independent FIFO ledger from exported ordered events, including reinsertion."""
    q = OrderedDict(); used = 0; hits = misses = nh = nm = peak = 0
    for e in r['cache_events']:
        t, size = e['tensor_id'], e['size_bytes']
        if e['event'] in ('hit', 'miss'):
            hit = t in q
            assert hit == (e['event'] == 'hit')
            if hit: hits += size; nh += 1
            else: misses += size; nm += 1
        else:
            assert e['event'] == 'insert' and t not in q and size <= r['cache_capacity_bytes']
            evicted = []
            while q and used + size > r['cache_capacity_bytes']:
                old, s = q.popitem(last=False); used -= s; evicted.append(old)
            q[t] = size; used += size; peak = max(peak, used)
            assert evicted == e['evicted_tensor_ids'] and used == e['used_bytes']
    s = r['cache_stats']
    assert (hits, misses, nh, nm) == (s['hit_bytes'], s['miss_bytes'], s['copy_in_hits'], s['copy_in_misses'])
    assert s['hit_rate'] == (hits/(hits+misses) if hits+misses else 0)
    assert used == r['cache_used_bytes_final'] and peak <= r['cache_capacity_bytes']
    assert list(q.items()) == [(e['tensor_id'], e['size_bytes']) for e in r['cache_final_entries']]
    paths = Counter(o.get('memory_path') for c in r['per_core_timeline'] for o in c['ops'] if o['op'] in ('COPY_IN','COPY_OUT'))
    assert not paths['ON_CHIP'], 'DDR-derived metric requires no on-chip COPY'
    return dict(fifo_ledger=True, peak_bytes=peak, hit_bytes=hits, miss_bytes=misses,
                physical_ddr_bytes_derived=r['data_movement_bytes']['scheduled_copy_bytes']-hits)


def audit(raw, plan, r, settings, delay):
    cache = audit_cache(r)
    profiles = PhysicalScorer(raw, settings, delay).actual_lifetimes(plan, r)
    return dict(cache=cache, global_memory_peak={str(c):p['peak_bytes'] for c,p in profiles.items()},
                synchronization=True, traffic_identity=True)


def cache_diagnostic(r):
    """Prioritize groups with repeated actual misses; no claimed causal savings."""
    events = [e for e in r['cache_events'] if e['event']=='miss']
    counts = Counter(e['tensor_id'] for e in events)
    groups = {(c['core_id'],o['op_id']):o['subgraph_id'] for c in r['per_core_timeline'] for o in c['ops']}
    score = Counter()
    for e in events:
        g = groups[e['core_id'],e['op_id']]
        if g is not None and counts[e['tensor_id']]>1: score[g] += e['size_bytes']*(counts[e['tensor_id']]-1)
    return dict(group_priority=sorted(score,key=lambda g:(-score[g],g)), hol=[], group_scores=dict(score))


def solve(raw, seed, settings, delay, cache, budget=8, mode='cache'):
    start=time.perf_counter(); anchor=evaluate(raw,seed,settings,delay,cache)
    best=copy.deepcopy(seed); result=anchor; rows=[]; seen={key(seed)}
    g=SceneBGraph(raw,settings,delay)
    diagnostic=cache_diagnostic(anchor) if mode=='cache' else None
    proposals=pool(g,seed,diagnostic,budget=budget) if budget else []
    for item in proposals:
        p=item['plan']; h=key(p)
        if h in seen: continue
        seen.add(h); t=time.perf_counter()
        try:
            r=evaluate(raw,p,settings,delay,cache)
            accept=(r['makespan'],r['data_movement_bytes']['added_copy_bytes']) < (result['makespan'],result['data_movement_bytes']['added_copy_bytes'])
            if accept: best,result=copy.deepcopy(p),r
            rows.append(dict(status='ok',plan_sha256=h,move=item['move'],makespan=r['makespan'],added_copy_bytes=r['data_movement_bytes']['added_copy_bytes'],hit_rate=r['cache_stats']['hit_rate'],accepted=accept,seconds=time.perf_counter()-t))
        except (RuntimeError,ValueError) as exc:
            rows.append(dict(status='invalid',plan_sha256=h,move=item['move'],error=str(exc),seconds=time.perf_counter()-t))
    search_seconds=time.perf_counter()-start
    replay=evaluate(raw,best,settings,delay,cache)
    assert replay==result
    checks=audit(raw,best,replay,settings,delay)
    return best,replay,anchor,dict(mode=mode,budget=budget,candidate_calls=len(rows),official_calls=len(rows)+2,
          search_seconds=search_seconds,total_seconds=time.perf_counter()-start,seed_plan_sha256=key(seed),
          selected_plan_sha256=key(best),replay_equal=True,checks=checks,evaluations=rows,diagnostic=diagnostic)

