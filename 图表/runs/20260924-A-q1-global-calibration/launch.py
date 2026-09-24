import json,subprocess,time,hashlib
from pathlib import Path
root=Path(__file__).resolve().parent
py='/home/xihs/q1-runtime/python-3.12.14/bin/python3.12'
base=Path('/home/xihs/q1-campaigns/ranking-full100-20260924-r01/validation/图表/runs/20260924-A-q1-ranking-full100')
prior=Path('/home/xihs/q1-campaigns/memory-routing-20260924-r01/validation/runs')
refs=[str(base),str(prior/'component_memory'),str(prior/'component_hybrid')]
protocol='审查/问题一全局成本校准协议_20260924.md'
spec=json.loads(Path('审查/问题一全局成本校准协议_20260924.json').read_text())
meta={'jobs':[],'completed':False};start=time.perf_counter()
def save():Path('execution.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2))
def run(name,cases,variants):
 cmd=[py,'-u','程序/q1_opportunity_campaign.py','--reference-run','references','--output','runs/'+name,'--workers','16','--variants',*variants,'--cases',*cases,'--protocol',protocol,'--verified-plan-runs',*refs]
 row={'name':name,'command':cmd};meta['jobs'].append(row);save()
 with open(name+'.log','w') as log:row['returncode']=subprocess.call(cmd,stdout=log,stderr=subprocess.STDOUT)
 save()
 if row['returncode']!=0:raise RuntimeError(name+' failed')
 return json.loads(Path('runs',name,'summary.json').read_text())
subprocess.run([py,'-m','unittest','discover','-s','程序/tests','-p','test_q1*.py'],stdout=open('tests.log','w'),stderr=subprocess.STDOUT,check=True)
all_dev=run('development',spec['development'],['routes_unguarded','routes_event_guarded'])
s=dict(all_dev,runs=[r for r in all_dev['runs'] if r['config']=='routes_event_guarded'])
control={(r['case'],r['cores']):r for r in all_dev['runs'] if r['config']=='routes_unguarded'}
old={(r['case'],r['cores']):r for r in json.loads((base/'summary.json').read_text())['runs']}
checks={'protection_no_regression':all(r['makespan']<=old[r['case'],r['cores']]['makespan'] for r in s['runs'] if r['case'] in ['case_028','case_067'])}
for name,cases in [('component_memory',['case_058','case_039','case_072']),('component_hybrid',['case_009','case_100','case_040'])]:
 before=sum(r['makespan'] for r in control.values() if r['case'] in cases)
 after=sum(r['makespan'] for r in s['runs'] if r['case'] in cases)
 checks[name]={'before':before,'after':after,'pass':after<=before}
proceed=checks['protection_no_regression'] and all(checks[n]['pass'] for n in ['component_memory','component_hybrid'])
Path('frozen_extension_decision.json').write_text(json.dumps({'proceed':proceed,'checks':checks,'rule':'frozen before development','code_sha256':s['code_sha256']},indent=2))
print('DEVELOPMENT_DECISION',proceed,checks,flush=True)
if proceed:run('extension',spec['extension'],['routes_unguarded','routes_event_guarded'])
meta.update(completed=True,extension_started=proceed,wall_seconds=time.perf_counter()-start);save()
print('ALL_DONE',flush=True)
