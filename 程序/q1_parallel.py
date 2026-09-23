"""Independent process-per-run evaluation; only the parent writes the summary."""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import gzip
import itertools
import json
import platform
from pathlib import Path
import sys
import time
from q1_io import PROCESSED, official, verify, sha, write_json
from q1_ablation import CONFIGS


def worker(job):
    case,cores,seed,config,budget,folder,sources = job
    for name,h in sources.items():
        if sha((Path(__file__).parent/name).read_bytes())!=h:
            raise RuntimeError('Source changed during parallel experiment')
    official()
    from evaluation_validation import read_evaluation_config
    from multicore_cut_evaluate_problem_1 import read_scene_a_config
    from q1_experimental import solve_experimental
    cfg = str(PROCESSED/'data/config.txt')
    raw = json.loads((PROCESSED/'data'/f'{case}.json').read_text(encoding='utf-8-sig'))
    plan,result,stats = solve_experimental(raw,read_evaluation_config(cfg),read_scene_a_config(cfg),
                                         cores,budget,seed,CONFIGS[config])
    out = Path(folder)/f'{case}_{cores}cores_seed{seed}_{config}'
    out.mkdir(exist_ok=False)
    write_json(out/'plan.json',plan); write_json(out/'search.json',stats)
    (out/'evaluation.json.gz').write_bytes(gzip.compress(
        json.dumps(result,ensure_ascii=False,separators=(',',':')).encode(),mtime=0))
    return {'case':case,'cores':cores,'seed':seed,'config':config,
            'makespan':result['makespan'],'speedup':stats['speedup'],
            'evaluations':len(stats['evaluations']),'seconds':stats['elapsed_seconds'],
            'official_calls':stats['official_calls'],'cache_hits':stats['cache_hits'],
            'budget_exhausted':stats['budget_exhausted'],
            'artifacts':{f.name:sha(f.read_bytes()) for f in out.iterdir()}}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--cases',nargs='+',required=True)
    ap.add_argument('--cores',nargs='+',type=int,default=[2,3,4,5])
    ap.add_argument('--seeds',nargs='+',type=int,default=[0,1])
    ap.add_argument('--configs',nargs='+',choices=[c for c in CONFIGS if CONFIGS[c] is not None],required=True)
    ap.add_argument('--evaluations',type=int,default=12)
    ap.add_argument('--workers',type=int,default=4)
    ap.add_argument('--output',type=Path,required=True)
    args = ap.parse_args()
    if args.workers<1 or args.evaluations<1 or any(c not in [2,3,4,5] for c in args.cores):
        ap.error('Invalid budget, workers or core count')
    for seq in [args.cases,args.cores,args.seeds,args.configs]:
        if len(seq)!=len(set(seq)): ap.error('Duplicate jobs')
    manifest = verify()
    inputs = {}
    for case in args.cases:
        p = PROCESSED/'data'/f'{case}.json'
        if not p.is_file() or p.parent.resolve()!=(PROCESSED/'data').resolve():
            ap.error('Invalid case')
        inputs[p.name] = sha(p.read_bytes())
    args.output.mkdir(parents=True,exist_ok=False)
    snapshot = args.output/'source_snapshot';snapshot.mkdir()
    sources = {}
    for p in Path(__file__).parent.glob('*.py'):
        (snapshot/p.name).write_bytes(p.read_bytes());sources[p.name]=sha(p.read_bytes())
    report = {'completed':False,'status':'prototype_parallel_ablation','python':platform.python_version(),
              'command':sys.argv,'workers':args.workers,'configs':{c:CONFIGS[c] for c in args.configs},
              'evaluation_budget':args.evaluations,'source_zip_sha256':manifest['source_sha256'],
              'input_sha256':inputs,'code_sha256':sources,'runs':[]}
    write_json(args.output/'summary.json',report)
    started = time.perf_counter()
    jobs = [(case,c,s,k,args.evaluations,str(args.output.resolve()),sources)
            for case,c,s,k in itertools.product(args.cases,args.cores,args.seeds,args.configs)]
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(worker,j):j for j in jobs}
        for future in as_completed(futures):
            try:
                row = future.result()
            except Exception as exc:
                report['failure'] = {'job':futures[future][:5],'error':repr(exc)}
                write_json(args.output/'summary.json',report)
                for f in futures: f.cancel()
                raise
            report['runs'].append(row)
            write_json(args.output/'summary.json',report)
            print(len(report['runs']), '/',len(jobs),row['case'],row['cores'],row['seed'],row['config'],row['makespan'],flush=True)
    report.update(completed=True,wall_seconds=time.perf_counter()-started,
                  all_budgets_exhausted=all(r['budget_exhausted'] for r in report['runs']))
    write_json(args.output/'summary.json',report)


if __name__=='__main__':
    main()
