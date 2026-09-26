from pathlib import Path
import sys,json,gzip,hashlib
R=Path.cwd();sys.path.insert(0,str(R/'程序'))
from q2_evaluator import load,evaluate
from q3_solver import audit_cache
O=R/'图表/runs/20260926-A-six-figures';O.mkdir(exist_ok=True)
B=R/'图表/runs/20260925-A-q23-full100-verified/jobs'
read=lambda p:json.loads(gzip.decompress(p.read_bytes())) if p.suffix=='.gz' else json.loads(p.read_text(encoding='utf-8-sig'))
s,d,prov=load();c=12
rawpath=R/f'数据/processed/q1/data/case_{c:03}.json';raw=read(rawpath)
job=B/f'q2_{c:03}';summary=read(job/'summary.json');seedpath=R/summary['arguments']['migration'];seed=read(seedpath)
base=evaluate(raw,seed,s,d);final=read(job/'final.evaluation.json.gz');replay=evaluate(raw,read(job/'final.plan.json'),s,d)
assert final['makespan']==replay['makespan'] and final['per_core_timeline']==replay['per_core_timeline']
assert base['makespan']>final['makespan']
q2=dict(case=c,cores=5,baseline=base,final=final,initial_plan=str(seedpath.relative_to(R)),final_plan=str((job/'final.plan.json').relative_to(R)),interpretation='Same scene-B official evaluator, declared input seed versus selected final plan; not a single-factor causal attribution.')
(O/'q2_trace.json').write_text(json.dumps(q2,ensure_ascii=False),encoding='utf-8')
p=B/'q3_039/final.evaluation.json.gz';res=read(p);audit=audit_cache(res);tid=1000000005
# Select the explicitly observed first resident/hit/eviction/miss episode.
ev=res['cache_events'];chosen=[]
for i,e in enumerate(ev):
 if (e['tensor_id']==tid or tid in e.get('evicted_tensor_ids',[])) and 39485<=e['time']<=78000:chosen.append(dict(index=i,**e))
q3=dict(case=39,cores=5,tensor_id=tid,cache_capacity_bytes=res['cache_capacity_bytes'],cache_bandwidth_bytes_per_cycle=res['cache_bandwidth_bytes_per_cycle'],events=chosen,audit=audit)
(O/'q3_events.json').write_text(json.dumps(q3,ensure_ascii=False,indent=2),encoding='utf-8')
sources=[rawpath,seedpath,job/'final.plan.json',job/'final.evaluation.json.gz',p,R/'output/allin2-q1-complete-20260926/all_case_results.csv',R/'图表/runs/20260924-A-q1-delivery-r02/all_case_results.csv']
(O/'sources.json').write_text(json.dumps({str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},ensure_ascii=False,indent=2),encoding='utf-8')
print('Q2:',base['makespan'],final['makespan']);print('Q3:',chosen)

