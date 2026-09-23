import json,subprocess,sys,time,zipfile,hashlib,platform,os
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'程序'))
from q1_io import verify,write_json

def main():
    manifest=verify();start=time.perf_counter()
    jobs=[]
    for name,extra,workers in [('20260924-A-q1-component-primary',['--cases']+['case_'+x for x in ['017','045','048','065','077','002','028','063','067','085','006','040','090','097']],12),('20260924-A-q1-component-robust',['--robustness'],4)]:
        output=ROOT/'图表/runs'/name
        cmd=[sys.executable,'-u',str(ROOT/'程序/q1_seed_campaign.py'),'--reference-run',str(ROOT/'references'),'--output',str(output),'--workers',str(workers),'--variants','shared_region','component_guard','component_slot','--protocol',str(ROOT/'审查/问题一分量预算优化实验协议_20260924.md')]+extra
        log=(ROOT/(name+'.log')).open('wb')
        p=subprocess.Popen(cmd,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
        jobs.append((name,p,log,cmd));print('STARTED',name,p.pid,flush=True)
    state=dict(host=platform.node(),python=platform.python_version(),logical_cpus=os.cpu_count(),workers=16,source_sha256=manifest['source_sha256'],jobs=[])
    for name,p,log,cmd in jobs:
        rc=p.wait();log.close();state['jobs'].append(dict(name=name,returncode=rc,command=cmd));print('EXIT',name,rc,flush=True)
    state['wall_seconds']=time.perf_counter()-start;state['completed']=all(j['returncode']==0 for j in state['jobs'])
    write_json(ROOT/'server_execution.json',state)
    with zipfile.ZipFile(ROOT/'results.zip','w',zipfile.ZIP_DEFLATED) as z:
        for name in ['server_execution.json','launch.py','input_package.json']:
            z.write(ROOT/name,name)
        for p in (ROOT/'图表/runs').rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts:z.write(p,p.relative_to(ROOT).as_posix())
        for p in ROOT.glob('*.log'):z.write(p,p.name)
    print('RESULTS_SHA256',hashlib.sha256((ROOT/'results.zip').read_bytes()).hexdigest(),flush=True)
    if not state['completed']:raise SystemExit(1)

if __name__=='__main__':main()
