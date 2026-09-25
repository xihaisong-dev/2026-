import sys,pathlib,json,hashlib,subprocess,time
from concurrent.futures import ThreadPoolExecutor,as_completed
sys.path.insert(0,'程序')
from q2_resources import snapshot
p=pathlib.Path('图表/runs/20260925-A-q23-cache-search');c=json.loads((p/'contract.json').read_text());(p/'rows').mkdir(exist_ok=True)
for f,h in c['sources'].items():assert hashlib.sha256(pathlib.Path(f).read_bytes()).hexdigest()==h,f
resources=snapshot();workers=max(1,min(12,resources['recommended_workers']));(p/'execution.json').write_text(json.dumps(dict(started_unix=time.time(),workers=workers,resources=resources)))
def run(q,i,kind,mode):
 name=f'q{q}_{i:03}_{kind}_{mode}';out=p/'jobs'/name;seconds=c['large_seconds'] if i in c['large_cases'] else c['small_seconds']
 args=['/home/xihs/q1-runtime/run-python','程序/q23_cache_search.py','--problem',str(q),'--graph',f'数据/processed/q1/data/case_{i:03}.json','--output',str(out),'--mode',mode,'--seconds',str(seconds),'--max-proposals','96','--cache-mib','32']
 if kind=='warm':args+=['--plan',f'图表/runs/20260925-A-q2-new-seeds/5cores/case_{i:03}_multicore_res.json' if q==2 else str(p/f'seeds/q3_{i:03}.json')]
 t=time.monotonic()
 try:r=subprocess.run(args,capture_output=True,text=True,timeout=615);code=r.returncode;error=r.stderr
 except subprocess.TimeoutExpired:code=-999;error='supervisor timeout'
 row=dict(problem=q,case=i,kind=kind,mode=mode,exitcode=code,external_seconds=time.monotonic()-t,error=error)
 if (out/'summary.json').exists():row['summary']=json.loads((out/'summary.json').read_text())
 (p/'rows'/(name+'.json')).write_text(json.dumps(row));print(json.dumps(dict(name=name,seconds=row['external_seconds'],valid=row.get('summary',{}).get('valid'),complete=row.get('summary',{}).get('complete'))),flush=True)
jobs=[(q,i,'warm',m) for q in [2,3] for i in c['warm_cases'][str(q)] for m in (['off','on'] if i%2 else ['on','off'])]+[(q,i,'cold','on') for q in [2,3] for i in c['cold_cases'][str(q)]]
jobs.sort(key=lambda x:x[1] not in c['large_cases'])
with ThreadPoolExecutor(max_workers=workers) as pool:
 for f in as_completed([pool.submit(run,*j) for j in jobs]):f.result()
(p/'execution_complete.json').write_text(json.dumps(dict(finished_unix=time.time(),jobs=len(jobs))))
