"""Replay the 500 submitted Q3 plans with the unchanged official Scene-B evaluator.

This adds the paired no-L2 evaluation of p^C; it never replaces the Q2 baseline.
"""
import argparse
import csv
import gzip
import json
import platform
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from q1_io import PROCESSED, ROOT, sha, verify, write_json
from q2_evaluator import evaluate, load

PLANS = ROOT / '图表/runs/20260924-A-q3-full-r02'
PAIRS = ROOT / '图表/runs/20260924-A-q3-delivery-r03/pairs.csv'


def replay(row):
    case, cores = int(row['case']), int(row['cores'])
    graph_path = PROCESSED / f'data/case_{case:03}.json'
    plan_path = PLANS / f'case_{case:03}/{cores}/case_{case:03}_multicore_res.json'
    raw = json.loads(graph_path.read_text(encoding='utf-8-sig'))
    plan = json.loads(plan_path.read_text(encoding='utf-8-sig'))
    settings, delay, _ = load()
    start = time.perf_counter()
    result = evaluate(raw, plan, settings, delay)
    assert result['num_cores'] == cores
    added = result['data_movement_bytes']['added_copy_bytes']
    assert added == int(row['selected_l2_added']), (case, cores, added)
    record = dict(case=case, cores=cores, q2_no_l2=int(row['no_l2']),
                  q2_plan_l2=int(row['fixed_l2']), q3_plan_no_l2=result['makespan'],
                  q3_plan_l2=int(row['selected_l2']), q3_plan_added=added,
                  q3_plan_cache_ratio=result['makespan']/int(row['selected_l2']),
                  graph_sha256=sha(graph_path.read_bytes()),
                  plan_sha256=sha(plan_path.read_bytes()),
                  evaluation_seconds=time.perf_counter()-start)
    return record, result


def appendix(rows, dest):
    lines = [r'\begin{longtable}{rrrrrr}',
             r'\caption{问题三逐用例两种方案与两种硬件配置的执行周期}\label{tab:q3-time}\\',
             r'\toprule 用例 & 核数 & Q2方案无L2 & Q2方案L2 & Q3方案无L2 & Q3方案L2\\\midrule',
             r'\endfirsthead',
             r'\toprule 用例 & 核数 & Q2方案无L2 & Q2方案L2 & Q3方案无L2 & Q3方案L2\\\midrule',
             r'\endhead']
    for r in rows:
        lines.append(f"{r['case']} & {r['cores']} & {r['q2_no_l2']} & {r['q2_plan_l2']} & {r['q3_plan_no_l2']} & {r['q3_plan_l2']} " + r'\\')
    lines += [r'\bottomrule', r'\end{longtable}']
    # Keep the original independently verified 500-row traffic/cache table.
    original=(ROOT/'图表/runs/20260924-A-q3-delivery-r03/appendix_table.tex').read_text(encoding='utf-8')
    marker='同方案的逻辑额外搬运量与无L2相同；无L2命中率不适用。'
    assert marker in original and original.count(r'\begin{longtable}')==2
    lines.append(original[original.index(marker):].rstrip())
    dest.write_text('\n'.join(lines)+'\n', encoding='utf-8')


def verify_existing(output):
    verify()
    with (output/'pairs.csv').open(encoding='utf-8', newline='') as f:
        rows=list(csv.DictReader(f))
    assert len(rows)==500 and {(int(r['case']),int(r['cores'])) for r in rows}=={(c,k) for c in range(1,101) for k in range(1,6)}
    for row in rows:
        case,cores=int(row['case']),int(row['cores'])
        path=output/f'case_{case:03}/{cores}'
        saved=json.loads((path/'metrics.json').read_text(encoding='utf-8'))
        with gzip.open(path/'official_no_l2.json.gz','rt',encoding='utf-8') as f: result=json.load(f)
        assert all(str(saved[k])==v for k,v in row.items())
        assert result['makespan']==int(row['q3_plan_no_l2'])
        assert result['data_movement_bytes']['added_copy_bytes']==int(row['q3_plan_added'])
        graph=PROCESSED/f'data/case_{case:03}.json'
        plan=PLANS/f'case_{case:03}/{cores}/case_{case:03}_multicore_res.json'
        assert sha(graph.read_bytes())==row['graph_sha256']
        assert sha(plan.read_bytes())==row['plan_sha256']
    report=dict(verified=True, count=500, official_results=500,
                source_pairs_sha256=sha(PAIRS.read_bytes()), output_pairs_sha256=sha((output/'pairs.csv').read_bytes()),
                appendix_sha256=sha((output/'appendix_table.tex').read_bytes()))
    write_json(output/'verification.json',report)
    print(json.dumps(report),flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--workers', type=int, default=6)
    p.add_argument('--verify-existing', action='store_true')
    a=p.parse_args()
    if a.verify_existing:
        verify_existing(a.output)
        return
    assert a.workers > 0 and not a.output.exists()
    manifest=verify()
    with PAIRS.open(encoding='utf-8-sig', newline='') as f: source=list(csv.DictReader(f))
    assert len(source)==500 and {(int(r['case']),int(r['cores'])) for r in source}=={(c,k) for c in range(1,101) for k in range(1,6)}
    a.output.mkdir(parents=True)
    write_json(a.output/'contract.json',dict(count=500, source_pairs_sha256=sha(PAIRS.read_bytes()),
               source_zip_sha256=manifest['source_sha256'], evaluator='official Scene B',
               python=platform.python_version(), workers=a.workers))
    records=[]
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        futures={pool.submit(replay,row):(int(row['case']),int(row['cores'])) for row in source}
        for f in as_completed(futures):
            case,cores=futures[f]
            record,result=f.result()
            path=a.output/f'case_{case:03}/{cores}'
            path.mkdir(parents=True)
            write_json(path/'metrics.json',record)
            with gzip.open(path/'official_no_l2.json.gz','wt',encoding='utf-8') as out:
                json.dump(result,out,ensure_ascii=False)
            records.append(record)
            if len(records)%25==0: print(f'{len(records)}/500',flush=True)
    records.sort(key=lambda r:(r['case'],r['cores']))
    with (a.output/'pairs.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
    appendix(records,a.output/'appendix_table.tex')
    summary=[]
    for k in range(1,6):
        v=[r for r in records if r['cores']==k]
        summary.append(dict(cores=k, count=len(v), q2_no_l2_total=sum(r['q2_no_l2'] for r in v),
                            q2_plan_l2_total=sum(r['q2_plan_l2'] for r in v),
                            q3_plan_no_l2_total=sum(r['q3_plan_no_l2'] for r in v),
                            q3_plan_l2_total=sum(r['q3_plan_l2'] for r in v),
                            same_plan_mean_ratio=sum(r['q3_plan_cache_ratio'] for r in v)/len(v)))
    write_json(a.output/'summary.json',dict(count=len(records), by_cores=summary,
               selected_plan_no_l2_wins=sum(r['q3_plan_no_l2']<r['q2_no_l2'] for r in records),
               selected_plan_no_l2_ties=sum(r['q3_plan_no_l2']==r['q2_no_l2'] for r in records)))
    print(json.dumps(summary,ensure_ascii=False),flush=True)


if __name__=='__main__': main()
