import pathlib,json,hashlib,subprocess,sys,time
from concurrent.futures import ThreadPoolExecutor,as_completed
p=pathlib.Path('图表/runs/20260925-A-q23-diagnostics');c=json.loads((p/'trial_contract.json').read_text())
for f,h in c['sources'].items():assert hashlib.sha256(pathlib.Path(f).read_bytes()).hexdigest()==h,f
py='/home/xihs/q1-runtime/run-python'
def one(problem,i,arm,bench=False):
 seed=f'图表/runs/20260925-A-q2-new-seeds/5cores/case_{i:03}_multicore_res.json' if problem==2 else str(p/f'seeds_q3/case_{i:03}.json')
 out=p/f'trials/q{problem}_{i:03}_{arm}'
 args=[py,'程序/q23_targeted_trial.py','--problem',str(problem),'--graph',f'数据/processed/q1/data/case_{i:03}.json','--plan',seed,'--output',str(out),'--arm',arm,'--seconds','90']
 if bench:args+=['--benchmark']
 r=subprocess.run(args,capture_output=True,text=True,timeout=300)
 print(json.dumps(dict(problem=problem,case=i,arm=arm,benchmark=bench,exitcode=r.returncode,output=r.stdout[-1500:],error=r.stderr[-1500:])),flush=True)
 return r.returncode
with ThreadPoolExecutor(max_workers=4) as pool:
 codes=[f.result() for f in as_completed([pool.submit(one,q,i,a) for q in [2,3] for i in c[f'q{q}_cases'] for a in c['arms']])]
assert not any(codes)
# Serial benchmarks avoid own campaign concurrency affecting timings.
for q,i in [(2,65),(2,33),(3,44),(3,5)]:assert one(q,i,'guided',True)==0
(p/'execution_complete.json').write_text(json.dumps({'finished_unix':time.time(),'trials':20,'benchmarks':4,'workers':4}))
