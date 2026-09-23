import json,subprocess,sys,time,zipfile,hashlib,platform,os
from pathlib import Path
ROOT=Path(__file__).resolve().parent
PY=sys.executable
CASES=['case_'+x for x in ['017','045','048','065','077','002','028','063','067','085','006','040','090','097']]
def load(p):return json.loads(p.read_text())
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2))
def archive(name):
 with zipfile.ZipFile(ROOT/name,'w',zipfile.ZIP_DEFLATED) as z:
  for p in (ROOT/'图表/runs').rglob('*'):
   if p.is_file():z.write(p,p.relative_to(ROOT).as_posix())
  for p in ROOT.iterdir():
   if p.is_file() and p.suffix in ['.json','.log','.py']:z.write(p,p.name)
 print(name,hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),flush=True)
def launch(name,extra,workers,variants):
 cmd=[PY,'-u',str(ROOT/'程序/q1_seed_campaign.py'),'--reference-run',str(ROOT/'references'),'--output',str(ROOT/'图表/runs'/name),'--workers',str(workers),'--variants']+variants+['--protocol',str(ROOT/'审查/问题一排序诊断与全量验证协议_20260924.md')]+extra
 log=(ROOT/(name+'.log')).open('wb');p=subprocess.Popen(cmd,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
 return p,log,dict(name=name,command=cmd,pid=p.pid)
def main():
 start=time.perf_counter();state=dict(python=platform.python_version(),cpu_count=os.cpu_count(),workers=16,jobs=[])
 jobs=[launch('20260924-A-q1-ranking-validation',['--cases']+CASES,12,['component_followup','component_local_rank']),launch('20260924-A-q1-ranking-robust',['--robustness'],4,['component_followup','component_local_rank'])]
 for p,log,item in jobs:
  item['returncode']=p.wait();log.close();state['jobs'].append(item);print('EXIT',item['name'],item['returncode'],flush=True)
 save(ROOT/'execution.json',state)
 if any(x['returncode'] for x in state['jobs']):raise RuntimeError('Validation incomplete; full100 not started')
 rows=load(ROOT/'图表/runs/20260924-A-q1-ranking-validation/summary.json')['runs'];base={(r['case'],r['cores']):r for r in rows if r['config']=='component_followup'}
 rr=[r for r in rows if r['config']=='component_local_rank'];dev=[r for r in rr if r['case'] in CASES[:10]];big={'case_028','case_063','case_067','case_085','case_097'}
 before=sum(base[r['case'],r['cores']]['makespan'] for r in dev);after=sum(r['makespan'] for r in dev)
 regressions=[r for r in rr if r['case'] in big and r['makespan']>base[r['case'],r['cores']]['makespan']]
 valid=all(r['verification_passed'] and r['evaluated_opportunities']==12 for r in rows)
 selected='component_local_rank' if after<before and not regressions and valid else 'component_followup'
 decision=dict(selected=selected,development_before=before,development_after=after,large_regressions=len(regressions),validation_ok=valid,rule='predeclared protocol; frozen before any full100 result',code_sha256=load(ROOT/'图表/runs/20260924-A-q1-ranking-validation/summary.json')['code_sha256'])
 save(ROOT/'frozen_selection.json',decision);print('FROZEN_SELECTION',json.dumps(decision,ensure_ascii=False),flush=True)
 archive('validation-results.zip')
 p,log,item=launch('20260924-A-q1-ranking-full100',['--cases']+[f'case_{i:03d}' for i in range(1,101)],16,[selected]);item['returncode']=p.wait();log.close();state['jobs'].append(item);state['wall_seconds']=time.perf_counter()-start;state['completed']=all(x['returncode']==0 for x in state['jobs']);save(ROOT/'execution.json',state)
 print('FULL100_EXIT',item['returncode'],flush=True);archive('all-results.zip')
 if not state['completed']:raise SystemExit(1)
if __name__=='__main__':main()
