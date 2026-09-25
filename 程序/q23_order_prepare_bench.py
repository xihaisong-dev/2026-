"""Fixed-work paired ordering benchmark; never an official speedup claim."""
import argparse,hashlib,json,time,platform
from pathlib import Path
import q2_solver as mod
from q23_selective_reuse import GenerationReuse
from q23_order_prepare import OrderingPreparation
from q3_solver import load
from q2_evaluator import key,evaluate

def run(out):
    out.mkdir(parents=True,exist_ok=False);s,d,cache,prov=load();rows=[];audit=[]
    def save():
        (out/'results.json').write_text(json.dumps(dict(rows=rows,audit=audit,platform=platform.platform(),provenance=prov,formal_promoted=False),ensure_ascii=False,indent=2),encoding='utf-8')
    for n in [33,67,72]:
        rawpath=Path(f'数据/processed/q1/data/case_{n:03}.json')
        seedpath=Path(f'图表/runs/20260925-A-q2-new-seeds/5cores/case_{n:03}_multicore_res.json')
        raw=json.loads(rawpath.read_text(encoding='utf-8'));seed=json.loads(seedpath.read_text(encoding='utf-8'))
        g=mod.SceneBGraph(raw,s,d);mapping={int(k):v for k,v in seed['node_to_subgraph'].items()};owners=mod.owner_of(seed)
        outputs={}
        for repeat in range(3):
            for arm in (['base','prepared'] if repeat%2==0 else ['prepared','base']):
                cls=GenerationReuse if arm=='base' else OrderingPreparation
                plans=[];times=[];t=time.perf_counter()
                with cls(g) as reuse:
                    for i in range(8):
                        shifted={v:(c+i)%5 for v,c in owners.items()}
                        # Distinct arguments defeat whole-result cache, same partition.
                        start=time.perf_counter();p=mod.order_plan(g,mapping,shifted,5,True,32,weight=[.25,.5,1,2][i%4]);times.append(time.perf_counter()-start);plans.append(p)
                hashes=[key(p) for p in plans]
                if outputs:assert hashes==outputs['hashes'],(n,arm,repeat)
                else:outputs=dict(hashes=hashes,plan=plans[0])
                rows.append(dict(case=n,repeat=repeat,arm=arm,seconds=time.perf_counter()-t,call_seconds=times,hashes=hashes,stats=dict(reuse.stats),
                    input_sha256=hashlib.sha256(rawpath.read_bytes()).hexdigest(),seed_sha256=hashlib.sha256(seedpath.read_bytes()).hexdigest()))
                save();print(n,repeat,arm,round(rows[-1]['seconds'],3),flush=True)
        # Final real candidate is independently evaluated with the original Q2 scorer.
        result=evaluate(raw,outputs['plan'],s,d)
        from q2_physical import PhysicalScorer
        PhysicalScorer(raw,s,d).actual_lifetimes(outputs['plan'],result)
        audit.append(dict(case=n,plan_sha256=key(outputs['plan']),makespan=result['makespan'],added=result['data_movement_bytes']['added_copy_bytes'],official=True))
        (out/f'case_{n:03}.plan.json').write_text(json.dumps(outputs['plan']),encoding='utf-8');save()
    summary=[]
    import statistics
    for n in [33,67,72]:
        a=[x['seconds'] for x in rows if x['case']==n and x['arm']=='base'];b=[x['seconds'] for x in rows if x['case']==n and x['arm']=='prepared']
        summary.append(dict(case=n,base_median=statistics.median(a),prepared_median=statistics.median(b),reduction_pct=100*(1-statistics.median(b)/statistics.median(a))))
    (out/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(summary)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();run(Path(a.output))
