import sys,pathlib,json,hashlib,subprocess,time
from concurrent.futures import ThreadPoolExecutor,as_completed
sys.path.insert(0,'程序')
from q2_resources import snapshot
p=pathlib.Path('图表/runs/20260925-A-q23-generation-long');c=json.loads((p/'contract.json').read_text());(p/'rows').mkdir(exist_ok=False)
for f,h in c['sources'].items():assert hashlib.sha256(pathlib.Path(f).read_bytes()).hexdigest()==h,f
resources=snapshot();workers=max(1,min(12,resources['recommended_workers']));(p/'execution.json').write_text(json.dumps(dict(resources=resources,workers=workers,started=time.time())))
def run(q,i,arm):
 out=p/'jobs'/f'q{q}_{i:03}_{arm}';seed=f'图表/runs/20260925-A-q2-new-seeds/5cores/case_{i:03}_multicore_res.json' if q==2 else f'图表/runs/20260925-A-q23-cache-search/seeds/q3_{i:03}.json'
 args=['/home/xihs/q1-runtime/run-python','程序/q23_cache_search.py','--problem',str(q),'--graph',f'数据/processed/q1/data/case_{i:03}.json','--plan',seed,'--output',str(out),'--mode','off','--seconds',str(c['seconds']),'--max-proposals',str(c['max_proposals']),'--seed',str(c['seed'])]
 if arm=='generation':args+=['--generation-reuse']
 t=time.monotonic()
 try:r=subprocess.run(args,capture_output=True,text=True,timeout=615);code=r.returncode;error=r.stderr
 except subprocess.TimeoutExpired:code=-999;error='outer supervisor timeout'
 row=dict(problem=q,case=i,arm=arm,seconds=time.monotonic()-t,exitcode=code,error=error,command=args)
 if (out/'summary.json').exists():row['summary']=json.loads((out/'summary.json').read_text())
 (p/'rows'/f'q{q}_{i:03}_{arm}.json').write_text(json.dumps(row));print(json.dumps(dict(job=out.name,seconds=row['seconds'],valid=row.get('summary',{}).get('valid'),complete=row.get('summary',{}).get('complete'))),flush=True)
jobs=[(int(q),i,a) for q,cs in c['cases'].items() for i in cs for a in (c['arms'] if i%2 else list(reversed(c['arms'])))];jobs.sort(key=lambda x:x[1] not in [67,72])
with ThreadPoolExecutor(max_workers=workers) as pool:
 for f in as_completed([pool.submit(run,*j) for j in jobs]):f.result()
(p/'complete.json').write_text(json.dumps(dict(count=len(jobs),ended=time.time(),resources=snapshot())))
