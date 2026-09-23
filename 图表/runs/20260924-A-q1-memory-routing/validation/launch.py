import subprocess,json,time
from pathlib import Path
root=Path(__file__).resolve().parent
py='/home/xihs/q1-runtime/python-3.12.14/bin/python3.12'
rows=[];handles=[];start=time.perf_counter()
for name,cases in [('component_memory',['case_058','case_039','case_072','case_028','case_067']),('component_hybrid',['case_009','case_100','case_040','case_028','case_067'])]:
 cmd=[py,'-u','程序/q1_seed_campaign.py','--reference-run','references','--output','runs/'+name,'--workers','6','--variants',name,'--cases',*cases,'--protocol','审查/问题一内存路由与主导分量验证协议_20260924.md']
 log=(root/(name+'.log')).open('w');p=subprocess.Popen(cmd,cwd=root,stdout=log,stderr=subprocess.STDOUT);rows.append(dict(command=cmd,pid=p.pid));handles.append((p,log))
(root/'execution.json').write_text(json.dumps(rows,indent=2))
for row,(p,log) in zip(rows,handles):row['returncode']=p.wait();log.close()
(root/'execution.json').write_text(json.dumps(dict(jobs=rows,seconds=time.perf_counter()-start),indent=2))
