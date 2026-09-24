"""Offline route diagnostics and isolated case091 search profiling."""
import argparse, cProfile, gzip, json, pstats, time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from q1_io import ROOT, PROCESSED, official, verify, write_json, sha


def context(case):
    official()
    from evaluation_validation import read_evaluation_config
    from multicore_cut_evaluate_problem_1 import read_scene_a_config
    config = str(PROCESSED/'data/config.txt')
    return json.loads((PROCESSED/'data'/f'{case}.json').read_text(encoding='utf-8-sig')), read_evaluation_config(config), read_scene_a_config(config)


def audit(job):
    case, cores, output = job
    raw, settings, waits = context(case)
    from q1_structural_seeds import GraphModel, guarded_component_candidate
    from q1_memory_routes import memory_pool, hybrid_pool
    from q1_local_rank import LocalRank
    from q1_experimental import CostGraph
    from q1_fast_evaluator import evaluate_scene_a
    m = GraphModel(raw, settings, waits)
    _, gate = guarded_component_candidate(raw, settings, waits, cores)
    pool = memory_pool(m, cores) if case in ['case_058','case_039','case_072'] else hybrid_pool(m, cores)
    # IDs select diagnostic coverage only, never solver dispatch.
    ranker = LocalRank(raw, CostGraph(raw, settings, waits, False))
    root = Path(output)/f'{case}_{cores}cores'; root.mkdir()
    rows = []
    for label, plan in pool:
        prediction, _, traffic = ranker.score(plan)
        tasks, _, movement, _ = ranker.preparer._build(raw, plan, **settings)
        row = dict(label=label, prediction=prediction, local_movement=movement,
                   local_tasks={s: {'step3': t['step3']} for s,t in tasks.items()})
        # Avoid huge operation traces: spill counters and local makespan suffice.
        row['local_tasks'] = {s:{k:v for k,v in t['step3'].items() if k in ['makespan','data_movement_bytes','memory_peak','spill_added_copy_bytes']} for s,t in tasks.items()}
        write_json(root/f'{label}_plan.json', plan); rows.append(row)
    write_json(root/'frozen_pool.json', dict(case=case, cores=cores, gate=gate, rows=rows, preparation=ranker.stats()))
    for row, (_, plan) in zip(rows, pool):
        start=time.perf_counter()
        result=evaluate_scene_a(raw,plan,**settings,cross_core_wait=waits['task_cross_core_wait_cycles'],same_core_wait=waits['task_same_core_wait_cycles'])
        row.update(makespan=result['makespan'],movement=result['data_movement_bytes'],memory_peak=result['memory_peak_by_core'],seconds=time.perf_counter()-start)
        (root/f"{row['label']}_evaluation.json.gz").write_bytes(gzip.compress(json.dumps(result).encode(),mtime=0))
    summary=dict(case=case,cores=cores,gate=gate['gate'],rows=rows,preparation=ranker.stats(),global_calls=len(rows))
    write_json(root/'summary.json',summary)
    return summary


def profile(output):
    raw, settings, waits = context('case_091')
    from q1_single_reference import reference
    from q1_experimental import solve_experimental
    from q1_ablation import CONFIGS
    single=json.loads(gzip.decompress((ROOT/'references/case_091/single/evaluation.json.gz').read_bytes()))
    fixed=reference(raw,settings,waits,single)
    pr=cProfile.Profile();start=time.perf_counter()
    plan,result,stats=pr.runcall(solve_experimental,raw,settings,waits,5,12,0,CONFIGS['component_local_rank'],single_reference=fixed,evaluator_backend='counter')
    root=Path(output);pr.dump_stats(str(root/'case091.prof'))
    with (root/'case091_profile.txt').open('w') as f:pstats.Stats(pr,stream=f).strip_dirs().sort_stats('cumtime').print_stats(55)
    write_json(root/'profile_result.json',dict(seconds=time.perf_counter()-start,plan=plan,makespan=result['makespan'],movement=result['data_movement_bytes'],stats=stats))


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);ap.add_argument('--profile',action='store_true');args=ap.parse_args()
    args.output.mkdir(parents=True,exist_ok=False);manifest=verify()
    write_json(args.output/'sources.json',{p.name:sha(p.read_bytes()) for p in Path(__file__).parent.glob('*.py')})
    if args.profile:profile(args.output);return
    jobs=[(c,k,str(args.output)) for c in ['case_058','case_039','case_072','case_009','case_100','case_040'] for k in [2,3,4,5]]
    rows=[]
    with ProcessPoolExecutor(max_workers=8) as pool:
        for f in as_completed([pool.submit(audit,j) for j in jobs]):
            rows.append(f.result());write_json(args.output/'summary.json',dict(completed=len(rows)==len(jobs),rows=rows));print('DONE',len(rows),flush=True)


if __name__=='__main__':main()
