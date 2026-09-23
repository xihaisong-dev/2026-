"""Frozen component-pool ranking and exact replay of the 12 missing slots."""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import gzip
import json
from pathlib import Path
import shutil
import time
from q1_io import PROCESSED, official, verify, write_json, sha
from q1_structural_seeds import guarded_component_candidate, initial_candidates, canonical_key
from q1_rank_metrics import metrics

CASES=['case_'+x for x in ['017','045','048','065','077','002','028','063','067','085','006','040','090','097']]

def symmetry_key(plan):
    groups={}
    for u,s in plan['node_to_subgraph'].items():groups.setdefault(s,[]).append(int(u))
    return tuple(sorted(tuple(tuple(sorted(groups[s])) for s in seq) for seq in plan['core_schedules']))

def inputs(case):
    official()
    from evaluation_validation import read_evaluation_config
    from multicore_cut_evaluate_problem_1 import read_scene_a_config
    config=str(PROCESSED/'data/config.txt')
    return (json.loads((PROCESSED/'data'/f'{case}.json').read_text(encoding='utf-8-sig')),
            read_evaluation_config(config),read_scene_a_config(config))

def pool_prepare(job):
    case,cores,out=job;raw,settings,waits=inputs(case)
    _,info=guarded_component_candidate(raw,settings,waits,cores)
    if info['gate']!='eligible':return dict(case=case,cores=cores,gate=info['gate'],rows=[])
    from q1_experimental import CostGraph
    from q1_search_tools import replay
    from q1_local_rank import LocalRank
    g=CostGraph(raw,settings,waits,False);g.fast_costs=True
    local=LocalRank(raw,g)
    candidates,_=initial_candidates(raw,settings,waits,cores,{'components'})
    ranked={x['candidate']:x for x in info['ranked']}
    rows=[];seen=set();folder=Path(out)/'pools'/f'{case}_{cores}cores';folder.mkdir(parents=True)
    for label,plan in candidates:
        k=canonical_key(plan)
        if k in seen:continue
        seen.add(k);r=ranked[label];mapping={int(u):s for u,s in plan['node_to_subgraph'].items()}
        proxy=replay(g,plan,g.costs(mapping)[0]);exact,duration,traffic=local.score(plan)
        pp=folder/f'{label}_plan.json';write_json(pp,plan)
        rows.append(dict(label=label,static=[r['compute_lower_bound'],r['input_read_bytes'],r['max_core_work']],proxy=proxy,
                         local=exact,duration=duration,plan_sha256=sha(pp.read_bytes())))
    assert local.stats()['global_evaluations']==0
    result=dict(case=case,cores=cores,gate=info['gate'],rows=rows,preparation=local.stats(),cost_state='empty local observations; raw graph/config frozen')
    write_json(folder/'predictions.json',result)
    return result

def pool_score(job):
    item,out=job;case=item['case'];cores=item['cores'];raw,settings,waits=inputs(case)
    from multicore_cut_evaluate_problem_1 import evaluate_scene_a
    folder=Path(out)/'pools'/f'{case}_{cores}cores';rows=[]
    for row in item['rows']:
        pp=folder/f"{row['label']}_plan.json";assert sha(pp.read_bytes())==row['plan_sha256']
        plan=json.loads(pp.read_text(encoding='utf8'));start=time.perf_counter()
        result=evaluate_scene_a(raw,plan,**settings,cross_core_wait=waits['task_cross_core_wait_cycles'],same_core_wait=waits['task_same_core_wait_cycles'])
        assert {int(s):d for s,d in row['duration'].items()}=={int(s):v['local_makespan'] for s,v in result['step3_by_task'].items()}
        ep=folder/f"{row['label']}_evaluation.json.gz";ep.write_bytes(gzip.compress(json.dumps(result,separators=(',',':')).encode(),mtime=0))
        rows.append(dict(row,official=result['makespan'],added_bytes=result['data_movement_bytes']['added_copy_bytes'],evaluation_seconds=time.perf_counter()-start,evaluation_sha256=sha(ep.read_bytes())))
    # Preserve actual deterministic generation order when predicted scores tie.
    def rank_stats(field):
        rr=[dict(row,sort_score=[row[field],i]) for i,row in enumerate(rows)]
        return metrics(rr,'sort_score')
    result=dict(item,rows=rows,rankings={x:rank_stats(x) for x in ['static','proxy','local']})
    write_json(folder/'outcomes.json',result);return result

def trace_worker(job):
    case,cores,prior,refs,out=job;raw,settings,waits=inputs(case)
    from q1_experimental import solve_experimental
    from q1_ablation import CONFIGS
    from q1_single_reference import reference
    base=Path(prior)/f'{case}_{cores}cores_seed0_component_followup'
    before=json.loads((base/'search.json').read_text(encoding='utf8'))
    single=json.loads(gzip.decompress((Path(refs)/case/'single/evaluation.json.gz').read_bytes()))
    frames=[]
    def capture(plan,label):frames.append((label,plan))
    plan,result,stats=solve_experimental(raw,settings,waits,cores,12,0,CONFIGS['component_followup'],single_reference=reference(raw,settings,waits,single),evaluator_backend='counter',on_proposal=capture)
    sig=lambda s:[(r['candidate'],r['makespan'],r['added_copy_bytes']) for r in s['evaluations']]
    assert sig(stats)==sig(before) and plan==json.loads((base/'plan.json').read_text(encoding='utf8'))
    assert len(frames)==len(stats['proposal_ledger'])
    seen=[];rows=[];folder=Path(out)/'traces'/f'{case}_{cores}cores';folder.mkdir(parents=True)
    for i,((label,p),record) in enumerate(zip(frames,stats['proposal_ledger'])):
        assert label==record['candidate']
        pp=folder/f'{i:03d}_plan.json';write_json(pp,p)
        if record['status']!='evaluated':continue
        category='novel';equiv=None
        for eid,previous in seen:
            if p==previous:category='raw_exact'
            elif canonical_key(p)==canonical_key(previous):category='task_renumber'
            elif symmetry_key(p)==symmetry_key(previous):category='core_permutation'
            else:continue
            equiv=eid;break
        eid=record['evaluation_id'];ev=stats['evaluations'][eid]
        improved=eid==0 or ev['makespan']<min(x['makespan'] for x in stats['evaluations'][:eid])
        rows.append(dict(label=label,evaluation_id=eid,classification=category,equivalent_id=equiv,makespan=ev['makespan'],incumbent_improved=improved,
                         equal_official_time=equiv is not None and ev['makespan']==stats['evaluations'][equiv]['makespan'],plan_sha256=sha(pp.read_bytes())))
        seen.append((eid,p))
    result=dict(case=case,cores=cores,trajectory_identical=True,full_score_calls=stats['official_calls'],fixed_reference_hits=stats['cache_hits'],rows=rows)
    write_json(folder/'search.json',stats);write_json(folder/'audit.json',result);return result

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for arg in ['prior','references','output','protocol']:ap.add_argument('--'+arg,type=Path,required=True)
    ap.add_argument('--workers',type=int,default=16);args=ap.parse_args();manifest=verify()
    args.output.mkdir(parents=True,exist_ok=False);snapshot=args.output/'source_snapshot';snapshot.mkdir()
    for p in Path(__file__).parent.glob('*.py'):shutil.copy2(p,snapshot/p.name)
    started=time.perf_counter();traces=[];trace_jobs=[];prepared=[]
    for p in sorted(args.prior.glob('*component_followup/search.json')):
        s=json.loads(p.read_text(encoding='utf8'));info=s['structural_seed_stats']
        if info.get('followup_unlocked') and info.get('followup_skip_reason')=='no_unprotected_opportunity_before_budget_end':
            case=p.parent.name[:8];cores=int(p.parent.name.split('_')[2][0]);trace_jobs.append((case,cores,str(args.prior),str(args.references),str(args.output)))
    assert len(trace_jobs)==12
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        fs={pool.submit(pool_prepare,(case,n,str(args.output))):'pool' for case in CASES for n in range(2,6)}
        fs.update({pool.submit(trace_worker,j):'trace' for j in trace_jobs})
        for f in as_completed(fs):
            r=f.result();(prepared if fs[f]=='pool' else traces).append(r)
        # All scores and pools committed before ANY new pool outcome is computed.
        write_json(args.output/'frozen_predictions.json',prepared)
        futures=[pool.submit(pool_score,(r,str(args.output))) for r in prepared if r['rows']]
        outcomes=[f.result() for f in as_completed(futures)]
    aggregate={}
    for field in ['static','proxy','local']:
        useful=[x for x in outcomes if len(x['rows'])>1]
        rho=[x['rankings'][field]['spearman'] for x in useful if x['rankings'][field]['spearman'] is not None]
        aggregate[field]=dict(pools=len(useful),defined_rho=len(rho),mean_spearman=sum(rho)/len(rho) if rho else None,
            top1_regret_sum=sum(x['rankings'][field]['top1_regret'] for x in useful),
            mean_relative_regret=sum(x['rankings'][field]['top1_regret']/min(r['official'] for r in x['rows']) for x in useful)/len(useful),
            top2_coverage=sum(x['rankings'][field]['top2_covers_best'] for x in useful)/len(useful))
    result=dict(completed=True,source_zip_sha256=manifest['source_sha256'],protocol_sha256=sha(args.protocol.read_bytes()),
        frozen_predictions_sha256=sha((args.output/'frozen_predictions.json').read_bytes()),code_sha256={p.name:sha(p.read_bytes()) for p in snapshot.glob('*.py')},
        pool_global_calls=sum(len(x['rows']) for x in outcomes),trace_global_calls=sum(x['full_score_calls'] for x in traces),trace_reference_hits=sum(x['fixed_reference_hits'] for x in traces),
        wall_seconds=time.perf_counter()-started,traces=traces,pools=outcomes,aggregate=aggregate)
    write_json(args.output/'summary.json',result);print(json.dumps({k:result[k] for k in ['pool_global_calls','trace_global_calls','aggregate']},ensure_ascii=False))

if __name__=='__main__':main()
