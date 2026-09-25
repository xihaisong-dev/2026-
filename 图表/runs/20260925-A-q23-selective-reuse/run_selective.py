import json,pathlib,hashlib,subprocess,time,sys
from concurrent.futures import ThreadPoolExecutor,as_completed
sys.path.insert(0,'程序')
from q2_resources import snapshot
p=pathlib.Path('图表/runs/20260925-A-q23-selective-reuse');c=json.loads((p/'contract.json').read_text());(p/'rows').mkdir(exist_ok=False)
for f,h in c['sources'].items():assert hashlib.sha256(pathlib.Path(f).read_bytes()).hexdigest()==h
resources=snapshot();workers=max(1,min(12,resources['recommended_workers']));(p/'execution.json').write_text(json.dumps(dict(resources=resources,workers=workers,started=time.time())))
def run(q,i,arm):
 gen,prep=c['arms'][arm];out=p/'jobs'/f'q{q}_{i:03}_{arm}'
 seed=f'图表/runs/20260925-A-q2-new-seeds/5cores/case_{i:03}_multicore_res.json' if q==2 else f'图表/runs/20260925-A-q23-cache-search/seeds/q3_{i:03}.json'
 args=['/home/xihs/q1-runtime/run-python','程序/q23_cache_search.py','--problem',str(q),'--graph',f'数据/processed/q1/data/case_{i:03}.json','--plan',seed,'--output',str(out),'--mode','on' if prep else 'off','--seconds',str(c['seconds_large'] if i in c['large_cases'] else c['seconds_small'])]
 if gen:args+=['--generation-reuse']
 if prep:args+=['--selective-preparation']
 t=time.monotonic();r=subprocess.run(args,capture_output=True,text=True,timeout=210)
 row=dict(problem=q,case=i,arm=arm,seconds=time.monotonic()-t,exitcode=r.returncode,error=r.stderr)
 if (out/'summary.json').exists():row['summary']=json.loads((out/'summary.json').read_text())
 (p/'rows'/f'q{q}_{i:03}_{arm}.json').write_text(json.dumps(row));print(json.dumps(row),flush=True)
jobs=[(int(q),i,a) for q,cs in c['cases'].items() for i in cs for a in c['arms']];jobs.sort(key=lambda x:x[1] not in c['large_cases'])
with ThreadPoolExecutor(max_workers=workers) as pool:
 for f in as_completed([pool.submit(run,*j) for j in jobs]):f.result()
(p/'complete.json').write_text(json.dumps(dict(count=len(jobs),ended=time.time())))
