import pathlib,json,hashlib,subprocess,time
from concurrent.futures import ThreadPoolExecutor,as_completed
while not pathlib.Path('../20260925-q23-preserved-r2/图表/runs/20260925-A-q23-preserved-r2/execution_complete.json').exists():time.sleep(2)
p=pathlib.Path('图表/runs/20260925-A-q23-preserved-r2b');c=json.loads((p/'contract.json').read_text())
for f,h in c['sources'].items():assert hashlib.sha256(pathlib.Path(f).read_bytes()).hexdigest()==h,f
py='/home/xihs/q1-runtime/run-python'
def one(q,i,arm,bench=False):
 seed=f'图表/runs/20260925-A-q2-new-seeds/5cores/case_{i:03}_multicore_res.json' if q==2 else f'图表/runs/20260925-A-q23-diagnostics/seeds_q3/case_{i:03}.json'
 out=p/f'trials/q{q}_{i:03}_{arm}'
 args=[py,'程序/q23_preserved_trial.py','--problem',str(q),'--graph',f'数据/processed/q1/data/case_{i:03}.json','--plan',seed,'--output',str(out),'--arm',arm,'--seconds','90']
 if bench:args+=['--benchmark']
 r=subprocess.run(args,capture_output=True,text=True,timeout=600)
 print(json.dumps(dict(problem=q,case=i,arm=arm,benchmark=bench,exitcode=r.returncode,output=r.stdout[-1500:],error=r.stderr[-1500:])),flush=True)
 assert r.returncode==0
 if not bench:
  summary=json.loads((out/'summary.json').read_text());assert summary['complete'] and summary['valid'] and not summary['error']
with ThreadPoolExecutor(max_workers=4) as pool:
 for f in as_completed([pool.submit(one,q,i,a) for q in [2,3] for i in c[f'q{q}_cases'] for a in c['arms']]):f.result()
# Reuse unchanged isolated r2 benchmarks; do not rerun or compete with them.
(p/'execution_complete.json').write_text(json.dumps(dict(finished_unix=time.time(),trials=20,benchmarks=0,workers=4)))
