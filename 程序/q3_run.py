"""Reproducible Q3 paired experiment; immutable directories and full official results."""
import argparse, csv, gzip, json, platform, time
from pathlib import Path
from q1_io import ROOT, PROCESSED, sha, write_json
from q2_evaluator import evaluate as evaluate_b
from q3_solver import load, solve

SEEDS=ROOT/'图表/runs/20260924-A-q2-delivery-r07/solutions'


def dump_gz(path,value):
    with gzip.open(path,'wt',encoding='utf-8') as f: json.dump(value,f,ensure_ascii=False)


def one(case,n,out,settings,delay,cache,budget,mode,seed_path=None):
    out.mkdir(parents=True,exist_ok=False); start=time.perf_counter()
    src=PROCESSED/f'data/case_{case:03}.json'
    raw=json.loads(src.read_text(encoding='utf-8-sig'))
    seed_path=seed_path or SEEDS/f'{n}cores/case_{case:03}_multicore_res.json'
    seed=json.loads(seed_path.read_text(encoding='utf-8-sig'))
    b=evaluate_b(raw,seed,settings,delay)
    plan,result,anchor,search=solve(raw,seed,settings,delay,cache,budget,mode)
    write_json(out/f'case_{case:03}_multicore_res.json',plan)
    write_json(out/'search.json',search)
    for name,r in [('no_l2',b),('fixed_l2',anchor),('selected_l2',result)]: dump_gz(out/f'{name}.json.gz',r)
    row=dict(case=case,cores=n,no_l2=b['makespan'],fixed_l2=anchor['makespan'],selected_l2=result['makespan'],
             hardware_ratio=b['makespan']/anchor['makespan'],combined_ratio=b['makespan']/result['makespan'],
             search_ratio=anchor['makespan']/result['makespan'],no_l2_added=b['data_movement_bytes']['added_copy_bytes'],
             fixed_l2_added=anchor['data_movement_bytes']['added_copy_bytes'],selected_l2_added=result['data_movement_bytes']['added_copy_bytes'],
             fixed_hit_rate=anchor['cache_stats']['hit_rate'],selected_hit_rate=result['cache_stats']['hit_rate'],
             fixed_hit_bytes=anchor['cache_stats']['hit_bytes'],fixed_miss_bytes=anchor['cache_stats']['miss_bytes'],
             selected_hit_bytes=result['cache_stats']['hit_bytes'],selected_miss_bytes=result['cache_stats']['miss_bytes'],
             search_seconds=search['search_seconds'],total_seconds=time.perf_counter()-start,input_sha256=sha(src.read_bytes()),seed_sha256=sha(seed_path.read_bytes()))
    assert row['no_l2_added']==row['fixed_l2_added']
    write_json(out/'metrics.json',row)
    return row


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cases',type=int,nargs='+',default=list(range(1,101)))
    p.add_argument('--cores',type=int,nargs='+',default=[1,2,3,4,5])
    p.add_argument('--budget',type=int,default=8)
    p.add_argument('--mode',choices=['cache','ordinary'],default='cache')
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args(); assert a.budget>=0 and all(1<=c<=100 for c in a.cases) and all(1<=n<=5 for n in a.cores)
    a.output.mkdir(parents=True,exist_ok=False)
    settings,delay,cache,provenance=load()
    write_json(a.output/'contract.json',dict(cases=a.cases,cores=a.cores,budget=a.budget,mode=a.mode,
               settings=settings,delay=delay,cache=cache,provenance=provenance,python=platform.python_version(),
               source_hashes={x.name:sha(x.read_bytes()) for x in (ROOT/'程序').glob('q3*.py')},
               seed_source='Q2 r07 c47a5986',stage_gate='NOT_RUN'))
    rows=[]
    for c in a.cases:
        for n in a.cores:
            row=one(c,n,a.output/f'case_{c:03}/{n}',settings,delay,cache,a.budget,a.mode)
            rows.append(row); write_json(a.output/'progress.json',rows)
            print(json.dumps({k:row[k] for k in ['case','cores','no_l2','fixed_l2','selected_l2','total_seconds']}),flush=True)
    with (a.output/'pairs.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    write_json(a.output/'completion.json',dict(complete=True,count=len(rows)))


if __name__=='__main__': main()
