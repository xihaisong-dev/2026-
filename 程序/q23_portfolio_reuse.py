"""Instrument frozen full portfolios; generation reuse is the only arm switch.

Search receives 80% of the wall budget; remaining time is reserved for original
replay and physical audit in BOTH arms. Original adaptive time policies remain.
"""
import argparse,contextlib,gzip,json,time,traceback
from pathlib import Path
from unittest.mock import patch
from q1_io import sha,write_json
from q2_timed_portfolio import atomic,objective
from q2_evaluator import key
from q23_cache_search import read,run as supervised_run

def worker(args,deadline):
    out=Path(args['output']);inner=out/'search';inner.mkdir();records=[];generation=None
    started=time.monotonic();q=args['problem']
    try:
        import q2_solver,q2_timed_portfolio,q3_timed_combination,q3_solver
        from q23_selective_reuse import GenerationReuse
        from q2_evaluator import evaluate as q2_evaluate
        from q2_physical import PhysicalScorer
        settings,delay,cache,provenance=q3_solver.load();raw=read(args['graph'])
        score=q2_evaluate if q==2 else q3_solver.evaluate
        def observed(*a,**kw):
            t=time.monotonic();h=key(a[1])
            r=score(*a,**kw)
            records.append(dict(plan_sha256=h,result_sha256=sha(json.dumps(r,sort_keys=True,separators=(',',':')).encode()),makespan=r['makespan'],added=objective(r)[1],seconds=time.monotonic()-t))
            atomic(out/'scored.json',records);return r
        source_args=dict(args,output=str(inner),arm='protected' if q==2 else 'combined')
        search_end=deadline-.2*args['seconds']
        source_graph=q2_solver.SceneBGraph
        with contextlib.ExitStack() as stack:
            def graph_factory(*a,**kw):
                nonlocal generation
                g=source_graph(*a,**kw)
                if args['reuse'] and generation is None:
                    generation=stack.enter_context(GenerationReuse(g))
                return g
            stack.enter_context(patch.object(q2_solver,'SceneBGraph',graph_factory))
            if q==2:
                stack.enter_context(patch.object(q2_timed_portfolio,'evaluate',observed))
                q2_timed_portfolio.worker(source_args,search_end)
            else:
                stack.enter_context(patch.object(q3_solver,'evaluate',observed))
                q3_timed_combination.worker(source_args,search_end)
        search_seconds=time.monotonic()-started
        if (inner/'error.txt').exists():raise RuntimeError((inner/'error.txt').read_text(encoding='utf-8'))
        pointer=read(inner/'verified.json');plan=read(inner/pointer['plan'])
        with gzip.open(inner/pointer['evaluation'],'rt',encoding='utf-8') as f:expected=json.load(f)
        t=time.monotonic()
        if q==2:
            result=q2_evaluate(raw,plan,settings,delay);assert json.loads(json.dumps(result))==expected
            PhysicalScorer(raw,settings,delay).actual_lifetimes(plan,result)
        else:
            result=q3_solver.evaluate(raw,plan,settings,delay,cache);assert json.loads(json.dumps(result))==expected
            q3_solver.audit(raw,plan,result,settings,delay)
        final_seconds=time.monotonic()-t
        write_json(out/'final.plan.json',plan)
        with gzip.open(out/'final.evaluation.json.gz','wt',encoding='utf-8') as f:json.dump(result,f)
        atomic(out/'verified.json',dict(plan='final.plan.json',evaluation='final.evaluation.json.gz',makespan=result['makespan'],added=objective(result)[1],plan_sha256=key(plan),official_original=True))
        atomic(out/'details.json',dict(search_seconds=search_seconds,final_verify_seconds=final_seconds,scored=records,generation_stats=dict(generation.stats) if generation else {},complete=True,
              input_sha256=sha(Path(args['graph']).read_bytes()),provenance=provenance,policy='Unmodified full protected/combined, including measured-time adaptive weights; sequence divergence is allowed'))
    except Exception:(out/'error.txt').write_text(traceback.format_exc(),encoding='utf-8')

def run(args):
    import q23_cache_search
    with patch.object(q23_cache_search,'worker',worker):return supervised_run(args)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--problem',type=int,required=True,choices=[2,3]);p.add_argument('--graph',required=True);p.add_argument('--output',required=True)
    p.add_argument('--migration');p.add_argument('--seed-plan');p.add_argument('--anchor');p.add_argument('--reuse',action='store_true')
    p.add_argument('--seconds',type=float,default=590);p.add_argument('--cores',type=int,default=5);p.add_argument('--seed',type=int,default=0);p.add_argument('--max-proposals',type=int,default=96)
    a=vars(p.parse_args());a['cache_mib']=32
    if a['problem']==3 and not a['seed_plan']:p.error('Q3 needs --seed-plan')
    print(json.dumps(run(a)))
