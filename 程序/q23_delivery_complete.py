"""Complete missing core counts and same-plan no-L2 evidence without changing solvers."""
import argparse,concurrent.futures,gzip,hashlib,json,os,signal,subprocess,sys,time,zipfile
from pathlib import Path
from q1_io import write_json,verify,official
from q2_resources import snapshot

def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def gz(p,x):
 with gzip.open(p,'wt',encoding='utf-8') as f:json.dump(x,f)
def worker(root,jid):
 c=read(root/'contract.json');j=c['jobs'][jid];q,n,k=j['problem'],j['case'],j['cores'];out=root/'jobs'/f'{jid:04}';out.mkdir(parents=True,exist_ok=False);started=time.monotonic()
 row=dict(**j,valid=False)
 try:
  from q2_evaluator import evaluate as b
  from q3_solver import load,evaluate as l2,audit
  from q2_physical import PhysicalScorer
  s,d,cache,prov=load()
  from stub_multicore_cut_and_schedule import validate_multicore_plan
  raw=read(j['graph']);solve_seconds=0.
  if j['mode']=='solve':
   from q23_portfolio_reuse import run
   args=dict(problem=q,graph=j['graph'],output=str(out/'solve'),cores=k,seconds=590,seed=0,max_proposals=384,reuse=True,cache_mib=32,migration=j.get('migration'),seed_plan=j.get('seed_plan'),anchor=j.get('anchor'))
   result=run(args);solve_seconds=result['total_seconds'];write_json(out/'solver_summary.json',result)
   assert result['valid'] and result['complete'] and not result['error'] and not result['deadline_stop'] and result['worker_exitcode']==0 and solve_seconds<=600
   p=read(out/'solve'/result['plan'])
   with gzip.open(out/'solve'/result['evaluation'],'rt',encoding='utf-8') as f:r=json.load(f)
  elif j['mode']=='single':
   from singlecore_evaluate import build_singlecore_plan
   p=build_singlecore_plan(raw);r=b(raw,p,s,d) if q==2 else l2(raw,p,s,d,cache)
   if q==2:PhysicalScorer(raw,s,d).actual_lifetimes(p,r)
   else:audit(raw,p,r,s,d)
  else:
   assert sha(j['plan'])==c['files'][j['plan']] and sha(j['evaluation'])==c['files'][j['evaluation']]
   p=read(j['plan'])
   with gzip.open(j['evaluation'],'rt',encoding='utf-8') as f:r=json.load(f)
   audit(raw,p,r,s,d)
  validate_multicore_plan(raw,p);assert len(p['core_schedules'])==k
  write_json(out/f'case_{n:03}_multicore_res.json',p);gz(out/'evaluation.json.gz',r)
  row.update(makespan=r['makespan'],added=r['data_movement_bytes']['added_copy_bytes'],single=c['single'][str(n)],solve_seconds=solve_seconds,provenance=prov)
  if q==3:
   t=time.monotonic();plain=b(raw,p,s,d);PhysicalScorer(raw,s,d).actual_lifetimes(p,plain);gz(out/'same_plan_no_l2.json.gz',plain)
   row.update(no_l2_makespan=plain['makespan'],no_l2_added=plain['data_movement_bytes']['added_copy_bytes'],cache_hit_rate=r['cache_stats']['hit_rate'],same_plan_cache_ratio=plain['makespan']/r['makespan'],paired_evaluation_seconds=time.monotonic()-t)
  if q==2 and k==1:assert r['makespan']==c['single'][str(n)]
  row.update(valid=True,plan_sha256=sha(out/f'case_{n:03}_multicore_res.json'),evaluation_sha256=sha(out/'evaluation.json.gz'))
 except Exception:
  import traceback
  row['error']=traceback.format_exc()
 row['total_seconds']=time.monotonic()-started;write_json(out/'row.json',row)

def campaign(root):
 c=read(root/'contract.json');verify()
 for p,h in c['files'].items():assert sha(p)==h,p
 (root/'rows').mkdir(exist_ok=False);resource=snapshot();workers=min(15,resource['recommended_workers']);assert workers>0;write_json(root/'resources.json',dict(snapshot=resource,workers=workers))
 def run(jid):
  cmd=[sys.executable,str(Path(__file__)),str(root),'--worker',str(jid)];t=time.monotonic();p=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
  try:stdout,stderr=p.communicate(timeout=2400)
  except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);stdout,stderr=p.communicate()
  path=root/'jobs'/f'{jid:04}'/'row.json';row=read(path) if path.exists() else dict(**c['jobs'][jid],valid=False,error='worker_failed_or_2400s_verification_timeout')
  row.update(command=cmd,returncode=p.returncode,wall=time.monotonic()-t,stdout=stdout,stderr=stderr);row['valid']=row['valid'] and p.returncode==0;write_json(root/'rows'/f'{jid:04}.json',row);return row
 done=[]
 with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
  futures=[ex.submit(run,i) for i in range(len(c['jobs']))]
  for f in concurrent.futures.as_completed(futures):
   row=f.result();done.append(row);progress=dict(expected=len(c['jobs']),finished=len(done),valid=sum(r['valid'] for r in done),failures=[(r['problem'],r['case'],r['cores'],r['mode']) for r in done if not r['valid']],formal_promoted=False)
   write_json(root/'progress.json',progress);print(progress['finished'],row['problem'],row['case'],row['cores'],row['mode'],row['valid'],flush=True)
 write_json(root/'complete.json',progress)
 hashes={p.relative_to(root).as_posix():sha(p) for p in root.rglob('*') if p.is_file()};write_json(root/'hashes.json',hashes)
 with zipfile.ZipFile(root.parent/(root.name+'-evidence.zip'),'w',zipfile.ZIP_DEFLATED) as z:
  for p in root.rglob('*'):
   if p.is_file():z.write(p,p.as_posix())
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--worker',type=int);a=p.parse_args()
 if a.worker is None:campaign(a.root)
 else:worker(a.root,a.worker)
