import concurrent.futures as cf
import gzip,hashlib,json,os,platform,sys,time,zipfile,shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'程序'))
from q1_io import verify,official,write_json
from q1_seed_campaign import worker

def resume_worker(job):
    case,cores,seed,name,output,sources=job
    for filename,expected in sources.items():
        if hashlib.sha256((ROOT/'程序'/filename).read_bytes()).hexdigest()!=expected:raise RuntimeError('Frozen source mismatch')
    campaign=Path(output).name;foldername=f'{case}_{cores}cores_seed{seed}_{name}'
    source=ROOT/'recovered'/campaign/foldername
    if not source.exists():
        row=worker(job)
        row.update(solve_timing_complete=True,search_execution_host=platform.node(),verification_host=platform.node(),server_new_score_calls=row['full_score_calls'])
        write_json(Path(output)/foldername/'row.json',row)
        return row
    dispatch=json.loads((ROOT/'dispatch.json').read_text(encoding='utf8'))
    for file,expected in dispatch['recovered'][campaign+'/'+foldername].items():
        if hashlib.sha256((source/file).read_bytes()).hexdigest()!=expected:raise RuntimeError('Recovery artifact mismatch')
    official()
    from evaluation_validation import read_evaluation_config
    from multicore_cut_evaluate_problem_1 import evaluate_scene_a,read_scene_a_config
    cfg=str(ROOT/'数据/processed/q1/data/config.txt');settings=read_evaluation_config(cfg);waits=read_scene_a_config(cfg)
    raw=json.loads((ROOT/'数据/processed/q1/data'/f'{case}.json').read_text(encoding='utf-8-sig'))
    folder=Path(output)/foldername;shutil.copytree(source,folder)
    plan=json.loads((folder/'plan.json').read_text(encoding='utf8'))
    stats=json.loads((folder/'search.json').read_text(encoding='utf8'))
    result=json.loads(gzip.decompress((folder/'evaluation.json.gz').read_bytes()))
    single=json.loads(gzip.decompress((Path(output)/'single'/case/'evaluation.json.gz').read_bytes()))
    if len(stats['evaluations'])!=12 or stats['protected_grain_attempts']!=[.5,1.,2.,.25]:raise RuntimeError('Recovery budget mismatch')
    best=min(stats['evaluations'],key=lambda x:(x['makespan'],x['added_copy_bytes']))
    if (best['makespan'],best['added_copy_bytes'])!=(result['makespan'],result['data_movement_bytes']['added_copy_bytes']):raise RuntimeError('Recovery winner mismatch')
    start=time.perf_counter()
    actual=evaluate_scene_a(raw,plan,**settings,cross_core_wait=waits['task_cross_core_wait_cycles'],same_core_wait=waits['task_same_core_wait_cycles'])
    seconds=time.perf_counter()-start;actual=json.loads(json.dumps(actual))
    checks={k:result[k]==actual[k] for k in ['makespan','data_movement_bytes','per_core_timeline','memory_peak_by_core','step3_by_task']}
    write_json(folder/'verification.json',checks)
    if not all(checks.values()):raise RuntimeError('Recovered official replay mismatch')
    row=dict(case=case,cores=cores,seed=seed,config=name,makespan=result['makespan'],single_makespan=single['makespan'],speedup=single['makespan']/result['makespan'],
        **{k:result['data_movement_bytes'][k] for k in ['added_copy_bytes','partition_added_copy_bytes','spill_added_copy_bytes']},
        evaluated_opportunities=12,full_score_calls=stats['official_calls'],fixed_reference_hits=stats['cache_hits'],verification_calls=1,verification_passed=True,
        solve_seconds=None,solve_timing_complete=False,search_internal_seconds=stats['elapsed_seconds'],solve_timing_basis='Outer stopwatch lost at interruption; internal timer excludes graph construction',verification_seconds=seconds,
        structural_evaluations=stats['structural_seed_stats'].get('evaluated',0),final_tasks=len(set(plan['node_to_subgraph'].values())),best_candidate=best['candidate'],
        search_recovered_from_local=True,search_execution_host='local',verification_host=platform.node(),server_new_score_calls=0,
        artifacts={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir()})
    write_json(folder/'row.json',row);return row

def main():
    verify();official()
    from evaluation_validation import read_evaluation_config
    from multicore_cut_evaluate_problem_1 import evaluate_scene_a,read_scene_a_config
    cfg=str(ROOT/'数据/processed/q1/data/config.txt')
    settings=read_evaluation_config(cfg);waits=read_scene_a_config(cfg)
    checks=[]
    for plan_path in sorted((ROOT/'crosscheck').glob('*/plan.json')):
        graph=json.loads((ROOT/'数据/processed/q1/data/case_085.json').read_text(encoding='utf-8-sig'))
        plan=json.loads(plan_path.read_text(encoding='utf8'))
        expected=json.loads(gzip.decompress((plan_path.parent/'evaluation.json.gz').read_bytes()))
        actual=evaluate_scene_a(graph,plan,**settings,cross_core_wait=waits['task_cross_core_wait_cycles'],same_core_wait=waits['task_same_core_wait_cycles'])
        actual=json.loads(json.dumps(actual))
        fields=['makespan','data_movement_bytes','per_core_timeline','memory_peak_by_core','step3_by_task']
        checked={k:expected[k]==actual[k] for k in fields}
        checks.append(dict(sample=plan_path.parent.name,checks=checked))
        if not all(checked.values()):raise RuntimeError('Cross-platform check failed')
    write_json(ROOT/'cross_platform.json',checks)
    dispatch=json.loads((ROOT/'dispatch.json').read_text(encoding='utf8'))
    start=time.perf_counter()
    state=dict(completed=False,python=platform.python_version(),host=platform.node(),workers=min(12,len(dispatch['jobs'])),
               runs=[],failures=[],cross_platform_checks=checks,expected=len(dispatch['jobs']),started_unix=time.time())
    write_json(ROOT/'server_summary.json',state)
    with cf.ProcessPoolExecutor(max_workers=state['workers']) as pool:
        futures={}
        for item in dispatch['jobs']:
            name=item['campaign'];case,n,seed,variant=item['args']
            output=ROOT/'results'/name;output.mkdir(parents=True,exist_ok=True)
            job=(case,n,seed,variant,str(output),dispatch['campaigns'][name]['code_sha256'])
            futures[pool.submit(resume_worker,job)]=item
        for future in cf.as_completed(futures):
            item=futures[future]
            try:
                row=future.result();state['runs'].append(dict(campaign=item['campaign'],row=row))
                print('DONE',len(state['runs']),row['case'],row['cores'],row['seed'],row['config'],row['makespan'],flush=True)
            except Exception as e:state['failures'].append(dict(job=item,error=repr(e)));print('FAILED',repr(e),flush=True)
            state['wall_seconds']=time.perf_counter()-start
            write_json(ROOT/'server_summary.json',state)
    state['completed']=len(state['runs'])==state['expected'] and not state['failures']
    write_json(ROOT/'server_summary.json',state)
    with zipfile.ZipFile(ROOT/'server_results.zip','w',zipfile.ZIP_DEFLATED) as z:
        for name in ['dispatch.json','cross_platform.json','server_summary.json']:
            z.write(ROOT/name,name)
        for p in (ROOT/'results').rglob('*'):
            if p.is_file() and 'single' not in p.parts:z.write(p,p.relative_to(ROOT).as_posix())
    print('RESULT_ZIP_SHA256',hashlib.sha256((ROOT/'server_results.zip').read_bytes()).hexdigest(),flush=True)
    if not state['completed']:raise SystemExit(1)

if __name__=='__main__':main()
