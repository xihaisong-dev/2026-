"""Bounded scene-B portfolio. Every accepted result is an ORIGINAL official replay.

The parent owns the end-to-end deadline. Optional migration is a declared warm
input, never advertised as cold seed generation. Fixed T1 is an external metric.
No Q1 task-duration cache is valid for scene B's whole-core preparation.
"""
import argparse, copy, gzip, json, math, multiprocessing as mp
import os, random, time, traceback
from pathlib import Path
from collections import defaultdict
from q1_io import PROCESSED, write_json, sha
from q2_evaluator import load, evaluate, key


def atomic(path, value):
    path = Path(path); tmp = path.with_suffix(path.suffix + '.tmp')
    write_json(tmp, value); os.replace(tmp, path)


def objective(result):
    return result['makespan'], result['data_movement_bytes']['added_copy_bytes']


def family_weights(m):
    """Feature-based priors only, no case IDs or saved answers."""
    fraction = max(map(len, m.components)) / max(1, len(m.ids))
    return dict(remap=2 if fraction > .5 else 1,
                granularity=2 if fraction > .5 else 1,
                order=1, joint=1, insert=1)


def generate(family, m, g, incumbent, n, rng, step):
    from q2_solver import place, order_plan, owner_of, context, proposal, DEFAULTS
    from q2_physical import candidate_pool
    mapping = {int(u): s for u, s in incumbent['node_to_subgraph'].items()}
    if family == 'packing':
        # Only partition/placement construction is inherited from A; accepted
        # costs always include B's whole-core scheduling and tensor lifetimes.
        from q1_timed_candidates import packing
        return packing(g,m.components,n,rng,step)
    if family == 'frontier':
        from q1_timed_candidates import frontier_mapping
        mapping=frontier_mapping(g,n,rng,step)
        owners=place(g,mapping,n,True,(.25,1.,4.)[step%3])
        return order_plan(g,mapping,owners,n,True,weight=.5)
    if family == 'remap':
        # Log-spaced trade-offs between parallel work and marginal tensor traffic.
        weight = (0., .25, .5, 1., 2., 4.)[step % 6]
        owners = place(g, mapping, n, True, weight)
        return order_plan(g, mapping, owners, n, step % 2 == 0, weight=.5)
    if family == 'granularity':
        # Relative topological windows scale with graph size and core count.
        count = n * (2, 4, 8, 16, 32)[step % 5]
        width = max(1, math.ceil(len(m.ids) / count))
        mapping = {u: i // width for i, u in enumerate(g.order)}
        owners = place(g, mapping, n, True, (.25, 1., 4.)[(step // 5) % 3])
        return order_plan(g, mapping, owners, n, True, weight=.5)
    if family == 'order':
        groups, _, _, _, _, _, ranks = context(g, mapping)
        priority = {s: ranks[s] * rng.uniform(.5, 1.5) for s in groups}
        return order_plan(g, mapping, owner_of(incumbent), n, step % 2 == 0,
                          weight=(.1, .5, 1., 2.)[step % 4], random_priority=priority)
    if family == 'insert':
        pool = candidate_pool(g, incumbent, rng, 'move', limit=4)
        return pool[step % len(pool)]['plan'] if pool else incumbent
    return proposal(g, incumbent, n, rng, 'CLJ', DEFAULTS, joint=step % 2 == 0)[0]


def worker(args, deadline):
    folder = Path(args['output']); rows = []; best = result = None; seen = set()
    started = time.perf_counter(); rng = random.Random(args['seed'])
    counters = defaultdict(int); gain = defaultdict(float); spent = defaultdict(float)
    def assess(label, plan):
        nonlocal best, result
        h = key(plan); t = time.perf_counter()
        if h in seen:
            rows.append(dict(name=label, plan_sha256=h, status='duplicate', seconds=0))
            return 0.
        seen.add(h)
        try:
            r = evaluate(raw, plan, settings, delay)
            before = result['makespan'] if result else None
            accepted = result is None or objective(r) < objective(result)
            improvement = max(0., (before-r['makespan'])/before) if before else 0.
            if accepted:
                # Immutable payloads first, atomic pointer last: timeout cannot
                # expose a new plan with an old official evaluation.
                name = 'accepted_%03d' % len(rows)
                write_json(folder/(name+'.plan.json'), plan)
                with gzip.open(folder/(name+'.evaluation.json.gz'), 'wt', encoding='utf-8') as f:
                    json.dump(r, f)
                atomic(folder/'verified.json', dict(plan=name+'.plan.json',
                    evaluation=name+'.evaluation.json.gz', makespan=r['makespan'],
                    added_copy_bytes=objective(r)[1], plan_sha256=h, official_original=True))
                best, result = copy.deepcopy(plan), r
            rows.append(dict(name=label, plan_sha256=h, status='ok', accepted=accepted,
                makespan=r['makespan'], added_copy_bytes=objective(r)[1], seconds=time.perf_counter()-t))
        except (ValueError, RuntimeError) as e:
            improvement = 0.; rows.append(dict(name=label, plan_sha256=h,
                status='invalid', error=str(e), seconds=time.perf_counter()-t))
        atomic(folder/'search.json', dict(evaluations=rows, elapsed=time.perf_counter()-started,
            counts=dict(counters), gain=dict(gain), spent=dict(spent)))
        return improvement
    try:
        settings, delay, provenance = load(args.get('config'))
        raw = json.loads(Path(args['graph']).read_text(encoding='utf-8'))
        from q1_structural_seeds import GraphModel, _component_plan
        from q2_solver import SceneBGraph
        from q2_reserve_shared import menu
        from q2_bottleneck_j import pool
        m = GraphModel(raw, settings, dict(task_cross_core_wait_cycles=delay, task_same_core_wait_cycles=0))
        g = SceneBGraph(raw, settings, delay); n = args['cores']
        migration = (json.loads(Path(args['migration']).read_text(encoding='utf-8'))
                     if args.get('migration') else _component_plan(m, n, 'pipe', True))
        atomic(folder/'identity.json', dict(input_sha256=sha(Path(args['graph']).read_bytes()),
            provenance=provenance, seed_mode='warm_Q1' if args.get('migration') else 'cold_components',
            migration_sha256=sha(Path(args['migration']).read_bytes()) if args.get('migration') else None,
            weights=family_weights(m), arguments=args))
        assess('migration_B' if args.get('migration') else 'components_bootstrap', migration)
        whole=dict(node_to_subgraph={str(u):0 for u in g.ops},core_schedules=[[0]]+[[] for _ in range(n-1)])
        seeds=[('whole',whole)]; metadata={}
        # Both arms keep the adopted seed menu and ordinary repair opportunities.
        _, more = menu(raw, settings, delay, n, migration, metadata); seeds += more
        for label, plan in seeds:
            if time.monotonic() >= deadline: return
            assess(label, plan)
        if best is None: raise RuntimeError('No verified fallback')
        for item in pool(g, best, None, budget=4):
            if time.monotonic() >= deadline: return
            assess('ordinary_J', item['plan'])
        if args['arm'] == 'baseline': return
        weights = family_weights(m)
        if args['arm']=='protected':
            weights['frontier']=1
            if len(m.components)>1: weights['packing']=2
        families = list(weights)
        adaptive_started=time.monotonic()
        protected_until=adaptive_started+.4*max(0,deadline-adaptive_started)
        # Finite proposal cap, not a combinatorial enumeration. Initial round
        # explores every family; subsequent draws retain minimum exploration.
        for iteration in range(args['max_proposals']):
            remaining = deadline-time.monotonic()
            recent = [r['seconds'] for r in rows if r['status']=='ok'][-4:]
            if remaining < max(.5, 1.3*max(recent, default=.1)): break
            protected=args['arm']=='protected' and iteration<32 and time.monotonic()<protected_until
            family = ('joint' if args['arm']=='ordinary_extended' or protected else
                families[iteration] if iteration<len(families) else rng.choices(
                families, [weights[f]*(1+min(8.,100*gain[f]/max(.1,spent[f]))) for f in families])[0])
            step=counters[family]; counters[family]+=1; t=time.perf_counter()
            try:
                candidate=generate(family,m,g,best,n,rng,step)
                gain[family]+=assess(family,candidate)
            except (ValueError,RuntimeError) as e:
                rows.append(dict(name=family,status='generation_invalid',error=str(e),seconds=time.perf_counter()-t))
            spent[family]+=time.perf_counter()-t
        atomic(folder/'search.json',dict(evaluations=rows,counts=dict(counters),gain=dict(gain),spent=dict(spent)))
    except Exception:
        (folder/'error.txt').write_text(traceback.format_exc(),encoding='utf-8')


def run(graph, output, cores=5, seconds=590, arm='portfolio', seed=0, migration=None, max_proposals=96):
    if not 2 <= cores <= 5 or not 0 < seconds <= 590: raise ValueError('cores 2..5, seconds (0,590]')
    if arm not in ('baseline','portfolio','ordinary_extended','protected'): raise ValueError(arm)
    started=time.monotonic(); folder=Path(output); folder.mkdir(parents=True,exist_ok=False)
    args=dict(graph=str(Path(graph).resolve()),output=str(folder.resolve()),cores=cores,
              seconds=seconds,arm=arm,seed=seed,migration=str(Path(migration).resolve()) if migration else None,
              max_proposals=max_proposals)
    ctx=mp.get_context('spawn'); process=ctx.Process(target=worker,args=(args,started+seconds))
    process.start(); process.join(max(0,seconds-(time.monotonic()-started)))
    stopped=process.is_alive()
    if stopped: process.terminate(); process.join(2)
    if process.is_alive(): process.kill(); process.join(2)
    pointer=folder/'verified.json'
    summary=dict(arguments=args,seconds=time.monotonic()-started,deadline_stop=stopped,
                 status='ok' if pointer.exists() else 'no_verified_solution',
                 worker_error=(folder/'error.txt').exists(), worker_exitcode=process.exitcode,
                 source_sha256={p.name:sha(p.read_bytes()) for p in Path(__file__).parent.glob('q*.py')})
    if pointer.exists(): summary.update(json.loads(pointer.read_text(encoding='utf-8')))
    atomic(folder/'summary.json',summary); return summary


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('graph');p.add_argument('--output',required=True)
    p.add_argument('--cores',type=int,default=5);p.add_argument('--seconds',type=float,default=590)
    p.add_argument('--arm',choices=['baseline','portfolio','ordinary_extended','protected'],default='portfolio');p.add_argument('--seed',type=int,default=0)
    p.add_argument('--migration');p.add_argument('--max-proposals',type=int,default=96)
    print(json.dumps(run(**vars(p.parse_args())),ensure_ascii=False,indent=2))
