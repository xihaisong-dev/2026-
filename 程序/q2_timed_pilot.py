"""Frozen five-core paired pilot; wall-clock caps, original replay validation."""
import argparse,csv,gzip,json,statistics,time
from pathlib import Path
from q1_io import ROOT,PROCESSED,write_json,sha
from q2_timed_portfolio import run
from q2_evaluator import load,evaluate


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',required=True,type=Path)
    ap.add_argument('--cases',nargs='+',type=int,default=[17,32,48,55,64,71,88])
    ap.add_argument('--seconds',type=float,default=60);a=ap.parse_args()
    a.output.mkdir(parents=True,exist_ok=False)
    source={p.name:sha(p.read_bytes()) for p in (ROOT/'程序').glob('q*.py')}
    settings,delay,provenance=load()
    baseline_path=ROOT/'图表/runs/20260924-A-q2-full-r07-shared-r08/pairs.csv'
    with baseline_path.open(encoding='utf-8-sig') as f:
        baseline={int(r['case']):r for r in csv.DictReader(f) if r['cores']=='5'}
    reference=json.loads((ROOT/'图表/runs/20260924-A-q2-full-r05/contract.json').read_text(encoding='utf-8'))['fixed_references']
    rows=[];arms=['baseline','ordinary_extended','portfolio']
    inputs={};seeds={}
    for i in a.cases:
        inputs[str(i)]=sha((PROCESSED/f'data/case_{i:03}.json').read_bytes())
        seeds[str(i)]=sha((ROOT/f'图表/runs/20260924-A-q1-delivery-r02/solutions/5cores/case_{i:03}_multicore_res.json').read_bytes())
    write_json(a.output/'contract.json',dict(cases=a.cases,cores=5,seconds=a.seconds,seed=0,max_proposals=96,
        arms=arms,sources=source,inputs=inputs,seeds=seeds,provenance=provenance,
        scope='warm shared Q1 seeds; solve includes load, generation, original evaluation, output; fixed T1 excluded',
        baseline='adopted seed menu + ordinary J; no padding evaluation; no full100 promotion',
        metrics='arithmetic mean of per-case fixed T1/T5; total cycles separately'))
    for index,i in enumerate(a.cases):
        graph=PROCESSED/f'data/case_{i:03}.json'
        migration=ROOT/f'图表/runs/20260924-A-q1-delivery-r02/solutions/5cores/case_{i:03}_multicore_res.json'
        for arm in (arms if index%2==0 else arms[::-1]):
            folder=a.output/f'case{i:03}-{arm}'
            s=run(graph,folder,seconds=a.seconds,arm=arm,migration=migration)
            row=dict(case=i,arm=arm,status=s['status'],seconds=s['seconds'],deadline_stop=s['deadline_stop'],
                     worker_error=s['worker_error'],old_makespan=int(baseline[i]['r07']),single=reference[f'case_{i:03}'])
            if s['status']=='ok':
                plan=json.loads((folder/s['plan']).read_text(encoding='utf-8'))
                with gzip.open(folder/s['evaluation'],'rt',encoding='utf-8') as f: saved=json.load(f)
                t=time.perf_counter();replay=evaluate(json.loads(graph.read_text(encoding='utf-8')),plan,settings,delay)
                # JSON serialization converts integer dictionary keys to strings.
                assert json.loads(json.dumps(replay))==saved
                row.update(makespan=s['makespan'],bytes=s['added_copy_bytes'],
                    speedup=row['single']/s['makespan'],independent_replay_equal=True,
                    external_validation_seconds=time.perf_counter()-t)
            rows.append(row);write_json(a.output/'rows.json',rows)
            print(json.dumps(row),flush=True)
    summary={}
    for arm in arms:
        subset=[r for r in rows if r['arm']==arm and r['status']=='ok']
        summary[arm]=dict(completed=len(subset),mean_speedup=statistics.mean(r['speedup'] for r in subset) if subset else None,
            total_cycles=sum(r['makespan'] for r in subset),total_bytes=sum(r['bytes'] for r in subset),
            max_seconds=max((r['seconds'] for r in subset),default=0))
    write_json(a.output/'summary.json',summary)


if __name__=='__main__':main()
