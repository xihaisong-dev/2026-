"""Frozen Q2/Q3 full100 campaign; separate directories, bounded verified workers."""
import argparse,concurrent.futures,gzip,hashlib,json,os,signal,subprocess,sys,time,zipfile
from pathlib import Path
from q2_resources import snapshot
from q1_io import write_json

def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def aggregate(root,c):
 rows=[read(p) for p in (root/'rows').glob('*.json')];arms={}
 for q in [2,3]:
  xs=[r for r in rows if r['problem']==q];ok=[r for r in xs if r['valid']]
  arms[str(q)]=dict(finished=len(xs),verified=len(ok),expected=100,failures=[r['case'] for r in xs if not r['valid']],complete=len(ok)==100)
  if ok:arms[str(q)].update(mean_speedup=sum(r['single']/r['makespan'] for r in ok)/len(ok),total_cycles=sum(r['makespan'] for r in ok),total_added=sum(r['added'] for r in ok),max_wall=max(r['wall'] for r in ok))
 result=dict(finished=len(rows),expected=200,problems=arms,partial=len(rows)<200,formal_promoted=False)
 write_json(root/'progress.json',result);return result

def run(root):
 c=read(root/'contract.json')
 for p,h in c['files'].items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h,p
 (root/'rows').mkdir(exist_ok=False)
 resource=snapshot();workers=min(c['workers'],resource['recommended_workers']);assert workers>0
 write_json(root/'resources.json',dict(snapshot=resource,workers=workers))
 def job(q,n):
  name=f'q{q}_{n:03}';out=root/'jobs'/name
  cmd=[sys.executable,'程序/q23_portfolio_reuse.py','--problem',str(q),'--graph',f'数据/processed/q1/data/case_{n:03}.json','--output',str(out),'--seconds',str(c['seconds']),'--cores','5','--seed',str(c['seed']),'--max-proposals',str(c['max_proposals']),'--reuse']
  if q==2:cmd+=['--migration',f'图表/runs/20260924-A-q1-delivery-r02/solutions/5cores/case_{n:03}_multicore_res.json']
  else:cmd+=['--seed-plan',f'图表/runs/20260925-A-q2-new-seeds/5cores/case_{n:03}_multicore_res.json','--anchor',f'图表/runs/20260924-A-q3-full-r02/case_{n:03}/5/case_{n:03}_multicore_res.json']
  row=dict(problem=q,case=n,command=cmd,valid=False,single=c['single'][str(n)]);t=time.monotonic()
  try:
   p=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
   try:stdout,stderr=p.communicate(timeout=620)
   except subprocess.TimeoutExpired:
    os.killpg(p.pid,signal.SIGKILL);stdout,stderr=p.communicate();row['error']='launcher_timeout'
   row.update(returncode=p.returncode,stdout=stdout,stderr=stderr,wall=time.monotonic()-t)
   if (out/'summary.json').exists():
    s=read(out/'summary.json');row['summary']=s
    row['valid']=bool(s.get('valid') and s.get('complete') and not s.get('error') and not s.get('deadline_stop') and s.get('worker_exitcode')==0 and p.returncode==0 and row['wall']<=600)
    if row['valid']:
     row.update(makespan=s['makespan'],added=s['added'],speedup=row['single']/s['makespan'],plan_file_sha256=hashlib.sha256((out/s['plan']).read_bytes()).hexdigest(),evaluation_file_sha256=hashlib.sha256((out/s['evaluation']).read_bytes()).hexdigest())
  except Exception as e:row.update(error=repr(e),wall=time.monotonic()-t)
  write_json(root/'rows'/(name+'.json'),row);return row
 jobs=c['jobs'];write_json(root/'queue.json',jobs)
 with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
  futures=[ex.submit(job,q,n) for q,n in jobs]
  for f in concurrent.futures.as_completed(futures):
   row=f.result();p=aggregate(root,c);print(p['finished'],row['problem'],row['case'],row['valid'],round(row['wall'],2),flush=True)
 write_json(root/'complete.json',aggregate(root,c))
 hashes={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
 write_json(root/'hashes.json',hashes)
 with zipfile.ZipFile(root.parent/(root.name+'-evidence.zip'),'w',zipfile.ZIP_DEFLATED) as z:
  for p in root.rglob('*'):
   if p.is_file():z.write(p,p.as_posix())
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('root');a=p.parse_args();run(Path(a.root))
