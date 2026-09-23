"""Frozen structural-seed ablation; independent jobs, fixed verified single refs."""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import gzip
import itertools
import json
from pathlib import Path
import platform
import shutil
import sys
import time
from q1_io import ROOT, PROCESSED, official, verify, sha, write_json
from q1_ablation import CONFIGS

CASES = ['case_017','case_045','case_048','case_065','case_077',
         'case_002','case_028','case_063','case_067','case_085']
VARIANTS = ['shared_region','seed_components','seed_batches','seed_depth','seed_combined']


def worker(job):
    case, cores, seed, name, output, sources = job
    for filename, expected in sources.items():
        if sha((Path(__file__).parent/filename).read_bytes()) != expected:
            raise RuntimeError('Source changed during frozen experiment')
    official()
    from evaluation_validation import read_evaluation_config
    from multicore_cut_evaluate_problem_1 import read_scene_a_config, evaluate_scene_a
    from q1_single_reference import reference
    from q1_experimental import solve_experimental
    cfg=str(PROCESSED/'data/config.txt')
    settings,waits=read_evaluation_config(cfg),read_scene_a_config(cfg)
    raw=json.loads((PROCESSED/'data'/f'{case}.json').read_text(encoding='utf-8-sig'))
    root=Path(output); folder=root/f'{case}_{cores}cores_seed{seed}_{name}'
    folder.mkdir(exist_ok=False)
    fixed_path=root/'single'/case/'evaluation.json.gz'
    single=json.loads(gzip.decompress(fixed_path.read_bytes()))
    fixed=reference(raw,settings,waits,single)
    start=time.perf_counter()
    plan,result,stats=solve_experimental(raw,settings,waits,cores,12,seed,CONFIGS[name],
                                         single_reference=fixed,evaluator_backend='counter')
    solve_seconds=time.perf_counter()-start
    write_json(folder/'plan.json',plan);write_json(folder/'search.json',stats)
    (folder/'evaluation.json.gz').write_bytes(gzip.compress(json.dumps(result,ensure_ascii=False,separators=(',',':')).encode(),mtime=0))
    if len(stats['evaluations'])!=12 or stats['protected_grain_attempts']!=[.5,1.,2.,.25]:
        raise RuntimeError('Budget or grain protection failed')
    # Exact replay is independent validation, never used for search selection.
    start=time.perf_counter()
    actual=evaluate_scene_a(raw,plan,**settings,cross_core_wait=waits['task_cross_core_wait_cycles'],
                            same_core_wait=waits['task_same_core_wait_cycles'])
    verification_seconds=time.perf_counter()-start
    norm=lambda x:json.loads(json.dumps(x,ensure_ascii=False))
    expected=norm(result);actual=norm(actual)
    fields=['makespan','data_movement_bytes','per_core_timeline','memory_peak_by_core','step3_by_task']
    checks={key:expected[key]==actual[key] for key in fields}
    write_json(folder/'verification.json',checks)
    if not all(checks.values()): raise RuntimeError('Original official replay mismatch')
    row=dict(case=case,cores=cores,seed=seed,config=name,makespan=result['makespan'],
             single_makespan=single['makespan'],speedup=single['makespan']/result['makespan'],
             added_copy_bytes=result['data_movement_bytes']['added_copy_bytes'],
             partition_added_copy_bytes=result['data_movement_bytes']['partition_added_copy_bytes'],
             spill_added_copy_bytes=result['data_movement_bytes']['spill_added_copy_bytes'],
             evaluated_opportunities=len(stats['evaluations']),full_score_calls=stats['official_calls'],
             fixed_reference_hits=stats['cache_hits'],verification_calls=1,verification_passed=True,
             solve_seconds=solve_seconds,verification_seconds=verification_seconds,
             structural_evaluations=stats['structural_seed_stats'].get('evaluated',0),
             final_tasks=len(set(plan['node_to_subgraph'].values())),
             best_candidate=min(stats['evaluations'],key=lambda x:(x['makespan'],x['added_copy_bytes']))['candidate'],
             artifacts={p.name:sha(p.read_bytes()) for p in folder.iterdir()})
    write_json(folder/'row.json',row)
    return row


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--reference-run',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--workers',type=int,default=12)
    ap.add_argument('--robustness',action='store_true',help='Predeclared seeds 1,2; baseline vs combined on 5 cores')
    args=ap.parse_args()
    if args.workers<1:ap.error('workers must be positive')
    manifest=verify(); previous=json.loads((args.reference_run/'summary.json').read_text(encoding='utf8'))
    if previous['source_zip_sha256']!=manifest['source_sha256']:raise ValueError('Source data mismatch')
    if previous['config_sha256']!=manifest['files']['data/config.txt']:raise ValueError('Config mismatch')
    args.output.mkdir(parents=True,exist_ok=False)
    snapshot=args.output/'source_snapshot';snapshot.mkdir()
    sources={}
    for p in Path(__file__).parent.glob('*.py'):
        snapshot.joinpath(p.name).write_bytes(p.read_bytes());sources[p.name]=sha(p.read_bytes())
    singles={}
    for case in CASES:
        if previous['input_sha256'][case+'.json']!=manifest['files']['data/'+case+'.json']:
            raise ValueError('Case hash mismatch')
        source=args.reference_run/case/'single'
        meta=json.loads((source/'row.json').read_text(encoding='utf8'))
        if sha((source/'evaluation.json.gz').read_bytes())!=meta['evaluation_sha256']:
            raise ValueError('Reference result corrupted')
        dest=args.output/'single'/case;dest.mkdir(parents=True)
        for filename in ['evaluation.json.gz','row.json']:
            shutil.copy2(source/filename,dest/filename)
        singles[case]=dict(makespan=meta['makespan'],result_sha256=meta['evaluation_sha256'])
    product=itertools.product(CASES,[5],[1,2],['shared_region','seed_combined']) if args.robustness else itertools.product(CASES,[2,3,4,5],[0],VARIANTS)
    jobs=[(case,n,seed,variant,str(args.output.resolve()),sources) for case,n,seed,variant in product]
    protocol=ROOT/'审查/问题一结构初解同预算实验协议_20260923.md'
    summary=dict(completed=False,command=sys.argv,python=platform.python_version(),workers=args.workers,
                 evaluation_budget=12,budget_unit='unique evaluated opportunities, including fixed reference reuse',
                 evaluator_backend='indexed-counter-v3, final original official A replay',
                 source_zip_sha256=manifest['source_sha256'],config_sha256=previous['config_sha256'],
                 input_sha256={c+'.json':manifest['files']['data/'+c+'.json'] for c in CASES},
                 code_sha256=sources,protocol_sha256=sha(protocol.read_bytes()),single_references=singles,
                 configs={name:CONFIGS[name] for name in VARIANTS},expected_runs=len(jobs),runs=[],failures=[])
    write_json(args.output/'summary.json',summary);start=time.perf_counter()
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures={pool.submit(worker,job):job[:4] for job in jobs}
        for future in as_completed(futures):
            try:row=future.result();summary['runs'].append(row)
            except Exception as e:summary['failures'].append(dict(job=futures[future],error=repr(e)))
            summary['wall_seconds']=time.perf_counter()-start
            write_json(args.output/'summary.json',summary)
            if len(summary['runs'])%10==0 or summary['failures']:
                print('DONE',len(summary['runs']),'/',len(jobs),'FAIL',len(summary['failures']),flush=True)
    summary['completed']=len(summary['runs'])==len(jobs) and not summary['failures']
    write_json(args.output/'summary.json',summary)
    if not summary['completed']:raise RuntimeError('Incomplete campaign; artifacts retained')


if __name__=='__main__':main()
