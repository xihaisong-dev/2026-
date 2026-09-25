import concurrent.futures,hashlib,json,pathlib,subprocess,time,sys
sys.path.insert(0,'程序')
from q2_resources import snapshot
root=pathlib.Path('图表/runs/20260925-A-q23-portfolio-reuse'); c=json.loads((root/'contract.json').read_text())
for section in ['sources','seeds']:
 for p,h in c[section].items():
  assert hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()==h,p
(root/'rows').mkdir(exist_ok=False)
resource=snapshot();(root/'resources.json').write_text(json.dumps(resource,indent=2))
def job(q,n,arm):
 name=f'q{q}_{n:03d}_{arm}'; out=root/'jobs'/name
 cmd=['/home/xihs/q1-runtime/run-python','程序/q23_portfolio_reuse.py','--problem',str(q),'--graph',f'数据/processed/q1/data/case_{n:03d}.json','--output',str(out),'--seconds','590','--cores','5','--seed','0','--max-proposals','96']
 if q==2:cmd+=['--migration',f'图表/runs/20260924-A-q1-delivery-r02/solutions/5cores/case_{n:03d}_multicore_res.json']
 else:cmd+=['--seed-plan',f'图表/runs/20260925-A-q2-new-seeds/5cores/case_{n:03d}_multicore_res.json','--anchor',f'图表/runs/20260924-A-q3-full-r02/case_{n:03d}/5/case_{n:03d}_multicore_res.json']
 if arm=='reuse':cmd+=['--reuse']
 t=time.monotonic();r=subprocess.run(cmd,capture_output=True,text=True,timeout=620)
 row=dict(problem=q,case=n,arm=arm,command=cmd,returncode=r.returncode,wall=time.monotonic()-t,stdout=r.stdout,stderr=r.stderr)
 p=out/'summary.json'
 if p.exists():row['summary']=json.loads(p.read_text())
 (root/'rows'/f'{name}.json').write_text(json.dumps(row,ensure_ascii=False,indent=2));print(name,r.returncode,round(row['wall'],2),flush=True)
 return row
jobs=[(q,n,a) for q in [2,3] for n in sorted(c['cases'][str(q)],reverse=True) for a in c['arms']]
with concurrent.futures.ThreadPoolExecutor(max_workers=min(12,max(1,resource.get('recommended_workers',12)))) as ex:
 results=list(ex.map(lambda x:job(*x),jobs))
(root/'complete.json').write_text(json.dumps(dict(count=len(results),jobs=jobs),indent=2))
