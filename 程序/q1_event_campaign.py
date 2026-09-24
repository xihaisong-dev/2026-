"""Disjoint host runner; full-case assignment is frozen in an explicit manifest."""
import argparse,json,subprocess,sys,time
from pathlib import Path
from q1_io import ROOT,write_json


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--host',choices=['local','server'],required=True);ap.add_argument('--phase',choices=['validation','full'],required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--reference-run',type=Path,required=True);ap.add_argument('--verified-plan-runs',nargs='*',default=[]);ap.add_argument('--manifest',type=Path);a=ap.parse_args()
    a.output.mkdir(parents=True,exist_ok=True);meta_path=a.output/f'{a.phase}_{a.host}_execution.json'
    if meta_path.exists():raise ValueError('Refusing to overwrite host execution')
    spec=json.loads((ROOT/'审查/问题一事件排序全量协议_20260924.json').read_text(encoding='utf8'))
    meta={'host':a.host,'phase':a.phase,'completed':False,'jobs':[]};start=time.perf_counter()
    def save():write_json(meta_path,meta)
    def run(name,cases,variants,cores=None):
        cmd=[sys.executable,'-u',str(ROOT/'程序/q1_opportunity_campaign.py'),'--reference-run',str(a.reference_run),'--output',str(a.output/name),'--workers',str(spec['workers'][a.host]),'--variants',*variants,'--cases',*cases,'--protocol',str(ROOT/'审查/问题一事件排序全量协议_20260924.md'),'--verified-plan-runs',*a.verified_plan_runs]
        if cores:cmd+=['--cores',*[str(x) for x in cores]]
        record={'name':name,'command':cmd};meta['jobs'].append(record);save()
        with (a.output/(name+'.log')).open('w',encoding='utf8') as f:record['returncode']=subprocess.call(cmd,stdout=f,stderr=subprocess.STDOUT)
        save()
        if record['returncode']:raise RuntimeError('Campaign failed: '+name)
    save()
    if a.phase=='validation':
        with (a.output/f'tests_{a.host}.log').open('w',encoding='utf8') as f:
            subprocess.run([sys.executable,'-m','unittest','discover','-s',str(ROOT/'程序/tests'),'-p','test_q1*.py'],stdout=f,stderr=subprocess.STDOUT,check=True)
        run('development_'+a.host,spec[a.host+'_development'],spec['development_variants'])
        run('extension_'+a.host,spec[a.host+'_extension'],spec['extension_variants'])
        if a.host=='server':run('crossplatform_server',['case_009'],['routes_event_reuse'],[2])
    else:
        manifest=json.loads(a.manifest.read_text(encoding='utf8'))
        cases=manifest['hosts'][a.host]['pending_cases']
        if cases:run('full_'+a.host,cases,[manifest['variant']])
    meta.update(completed=True,wall_seconds=time.perf_counter()-start);save();print('HOST_DONE',a.host,a.phase,flush=True)

if __name__=='__main__':main()
