"""Frozen holdout experiment launcher; never overwrite an existing campaign."""
import concurrent.futures, hashlib, json, pathlib, subprocess, time, sys
sys.path.insert(0,'程序')
from q2_resources import snapshot
root=pathlib.Path('图表/runs/20260925-A-q3-reward-holdout')
c=json.loads((root/'contract.json').read_text(encoding='utf-8'))
for section in ['sources','inputs']:
 for p,h in c[section].items():
  assert hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()==h,p
(root/'rows').mkdir(exist_ok=False)
resource=snapshot();workers=min(c['workers'],resource['recommended_workers'])
assert workers>0
(root/'resources.json').write_text(json.dumps(dict(snapshot=resource,workers=workers),indent=2))
def job(n,seed,arm):
 name=f'q3_{n:03d}_s{seed}_{arm}';out=root/'jobs'/name
 cmd=[sys.executable,'程序/q23_reward_prefix.py','--problem','3','--graph',f'数据/processed/q1/data/case_{n:03d}.json','--output',str(out),'--seconds',str(c['seconds']),'--cores',str(c['cores']),'--seed',str(seed),'--max-proposals',str(c['max_proposals']),'--seed-plan',f'图表/runs/20260925-A-q2-new-seeds/5cores/case_{n:03d}_multicore_res.json','--anchor',f'图表/runs/20260924-A-q3-full-r02/case_{n:03d}/5/case_{n:03d}_multicore_res.json','--policy',arm]
 t=time.monotonic();row=dict(case=n,seed=seed,arm=arm,command=cmd)
 try:
  r=subprocess.run(cmd,capture_output=True,text=True,timeout=620)
  row.update(returncode=r.returncode,stdout=r.stdout,stderr=r.stderr)
 except subprocess.TimeoutExpired as e:row.update(returncode=-1,error='launcher_timeout')
 except Exception as e:row.update(returncode=-2,error=repr(e))
 row['wall']=time.monotonic()-t
 p=out/'summary.json'
 if p.exists():row['summary']=json.loads(p.read_text(encoding='utf-8'))
 (root/'rows'/f'{name}.json').write_text(json.dumps(row,ensure_ascii=False,indent=2),encoding='utf-8')
 print(name,row['returncode'],round(row['wall'],2),flush=True)
 return row
# Pair adjacent arms, reverse their order for alternating case/seed to reduce order bias.
jobs=[(n,s,a) for n in [68,24,69,13,2,1] for s in c['seeds'] for a in (c['arms'] if (n+s)%2 else list(reversed(c['arms'])))]
(root/'queue.json').write_text(json.dumps(jobs,indent=2))
with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
 results=list(ex.map(lambda x:job(*x),jobs))
(root/'complete.json').write_text(json.dumps(dict(count=len(results),jobs=jobs),indent=2))
