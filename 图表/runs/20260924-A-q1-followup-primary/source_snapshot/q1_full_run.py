"""Frozen all-case initial-partition experiment; independent artifacts per run."""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import gc
import gzip
import json
from pathlib import Path
import platform
import sys
import time
from q1_io import PROCESSED, official, verify, sha, write_json
from q1_ablation import CONFIGS


def save_result(folder,result):
    (folder/'evaluation.json.gz').write_bytes(gzip.compress(
        json.dumps(result,ensure_ascii=False,separators=(',',':')).encode(),mtime=0))


def run_case(job):
    case,budget,output,sources,reuse_run=job
    for name,h in sources.items():
        if sha((Path(__file__).parent/name).read_bytes())!=h:
            raise RuntimeError('Source changed during campaign')
    official()
    from evaluation_validation import read_evaluation_config
    from multicore_cut_evaluate_problem_1 import read_scene_a_config
    from singlecore_evaluate import evaluate_singlecore
    from q1_experimental import solve_experimental
    raw=json.loads((PROCESSED/'data'/f'{case}.json').read_text(encoding='utf-8-sig'))
    settings=read_evaluation_config(str(PROCESSED/'data/config.txt'))
    waits=read_scene_a_config(str(PROCESSED/'data/config.txt'))
    caseout=Path(output)/case;caseout.mkdir(exist_ok=False)
    started=time.perf_counter()
    prior=Path(reuse_run)/case/'single' if reuse_run else None
    reused=False
    from q1_full_resume import verify_sources,restore,restore_cache
    if reuse_run:
        verify_sources(json.loads((Path(reuse_run)/'summary.json').read_text(encoding='utf-8')))
    if prior and (prior/'row.json').exists():
        old=json.loads((prior/'row.json').read_text(encoding='utf-8'))
        assert sha((prior/'evaluation.json.gz').read_bytes())==old['evaluation_sha256']
        prior_summary=json.loads((Path(reuse_run)/'summary.json').read_text(encoding='utf-8'))
        assert prior_summary['input_sha256'][case+'.json']==sha((PROCESSED/'data'/f'{case}.json').read_bytes())
        assert prior_summary['config_sha256']==sha((PROCESSED/'data/config.txt').read_bytes())
        single=json.loads(gzip.decompress((prior/'evaluation.json.gz').read_bytes()));reused=True
    else:
        single=evaluate_singlecore(raw,settings['bandwidth'],settings['capacity'],
            waits['task_cross_core_wait_cycles'],waits['task_same_core_wait_cycles'])
    from q1_single_reference import reference
    fixed_reference=reference(raw,settings,waits,single)
    reference_seconds=time.perf_counter()-started
    origin=str(caseout/'single')
    if reused:
        origin=str(prior)
        trace=old
        while trace.get('reused_from'):
            origin=trace['reused_from'];trace=json.loads((Path(origin)/'row.json').read_text(encoding='utf-8'))
        reference_seconds=trace.get('reference_compute_seconds',trace['seconds'])
    fixed=single['makespan'];singleout=caseout/'single';singleout.mkdir()
    save_result(singleout,single)
    single_row={'case':case,'cores':1,'config':'fixed_single','makespan':fixed,
        'speedup':1.,'official_calls':int(not reused),'reused_from':str(prior) if reused else None,'seconds':time.perf_counter()-started,
        'reference_compute_seconds':reference_seconds,'reference_origin':origin,
        'added_copy_bytes':single['data_movement_bytes']['added_copy_bytes'],
        'evaluation_sha256':sha((singleout/'evaluation.json.gz').read_bytes())}
    write_json(singleout/'row.json',single_row);del single;gc.collect()
    restore_cache(Path(reuse_run)/case/'evaluation_cache' if reuse_run else None,caseout/'evaluation_cache')
    rows=[]
    for cores in [2,3,4,5]:
        # Fixed order is recorded; timing is observational, not a timing benchmark.
        for config in ['shared_region','shared_resource']:
            out=caseout/f'{cores}cores_{config}'
            restored=restore(Path(reuse_run)/case/out.name if reuse_run else None,out,fixed)
            if restored is not None:
                rows.append(restored);print(case,cores,config,'RESUMED',flush=True);continue
            out.mkdir()
            plan,result,stats=solve_experimental(raw,settings,waits,cores,budget,0,CONFIGS[config],cache_dir=caseout/'evaluation_cache',single_reference=fixed_reference)
            if stats['singlecore_makespan']!=fixed:raise RuntimeError('Singlecore denominator changed')
            write_json(out/'plan.json',plan);write_json(out/'search.json',stats);save_result(out,result)
            row={'case':case,'cores':cores,'seed':0,'config':config,'makespan':result['makespan'],
                 'singlecore_makespan':fixed,'speedup':fixed/result['makespan'],
                 'official_calls':stats['official_calls'],'calls_this_attempt':stats['official_calls'],'cache_hits':stats['cache_hits'],'evaluated_opportunities':len(stats['evaluations']),'seconds':stats['elapsed_seconds'],
                 'budget_exhausted':stats['budget_exhausted'],
                 'added_copy_bytes':result['data_movement_bytes']['added_copy_bytes'],
                 'artifacts':{p.name:sha(p.read_bytes()) for p in out.iterdir()}}
            write_json(out/'row.json',row);rows.append(row)
            print(case,cores,config,row['makespan'],round(row['seconds'],2),'sec',flush=True)
            del plan,result,stats;gc.collect()
    return {'case':case,'single':single_row,'runs':rows}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--workers',type=int,default=4)
    ap.add_argument('--large-workers',type=int,default=1)
    ap.add_argument('--evaluations',type=int,default=12)
    ap.add_argument('--reuse-singles-from','--resume-from',dest='reuse_singles_from',type=Path)
    args=ap.parse_args()
    if not 0<args.large_workers<args.workers:ap.error('Need small and large worker slots')
    manifest=verify();cases=sorted(manifest['cases'],key=lambda x:(-x['ops'],x['case']))
    assert len(cases)==100
    args.output.mkdir(parents=True,exist_ok=False)
    snap=args.output/'source_snapshot';snap.mkdir()
    sources={}
    for p in Path(__file__).parent.glob('*.py'):
        (snap/p.name).write_bytes(p.read_bytes());sources[p.name]=sha(p.read_bytes())
    report={'completed':False,'status':'prototype_all_case_ablation','command':sys.argv,
        'python':platform.python_version(),'source_zip_sha256':manifest['source_sha256'],
        'input_sha256':{r['case']:manifest['files']['data/'+r['case']] for r in cases},
        'config_sha256':manifest['files']['data/config.txt'],'code_sha256':sources,
        'configs':{c:CONFIGS[c] for c in ['shared_region','shared_resource']},
        'workers':args.workers,'large_workers':args.large_workers,'large_threshold_ops':10000,
        'evaluation_budget':args.evaluations,'seed':0,'cases':[],'failures':[],
        'reuse_singles_from':str(args.reuse_singles_from) if args.reuse_singles_from else None,
        'budget_unit':'12 evaluated opportunities including exact cache hits; cache grants no extra candidates'}
    write_json(args.output/'summary.json',report);started=time.perf_counter()
    with ProcessPoolExecutor(max_workers=args.large_workers,max_tasks_per_child=1) as large, \
         ProcessPoolExecutor(max_workers=args.workers-args.large_workers,max_tasks_per_child=1) as small:
        futures={}
        for r in cases:
            name=Path(r['case']).stem
            pool=large if r['ops']>=10000 else small
            futures[pool.submit(run_case,(name,args.evaluations,str(args.output.resolve()),sources,str(args.reuse_singles_from.resolve()) if args.reuse_singles_from else None))]=name
        for f in as_completed(futures):
            try:report['cases'].append(f.result())
            except Exception as exc:report['failures'].append({'case':futures[f],'error':repr(exc)})
            report['wall_seconds']=time.perf_counter()-started
            write_json(args.output/'summary.json',report)
            print('CASES',len(report['cases']),'FAILURES',len(report['failures']),flush=True)
    report['completed']=len(report['cases'])==100 and not report['failures']
    write_json(args.output/'summary.json',report)
    if not report['completed']:raise RuntimeError('Incomplete campaign; partial artifacts retained')


if __name__=='__main__':main()
