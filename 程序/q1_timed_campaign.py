"""Parallel development campaign for timed portfolio; explicit warm/cold provenance."""
import argparse,json,subprocess,sys,time
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
from q1_io import ROOT,PROCESSED,write_json

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--cases',nargs='+',type=int,required=True);ap.add_argument('--cores',nargs='+',type=int,default=[5]);ap.add_argument('--seconds',type=float,default=60);ap.add_argument('--workers',type=int,default=4);ap.add_argument('--cold',action='store_true');ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    a.output.mkdir(parents=True,exist_ok=False);jobs=[(c,k) for c in a.cases for k in a.cores]
    write_json(a.output/'protocol.json',dict(cases=a.cases,cores=a.cores,seconds=a.seconds,workers=a.workers,cold=a.cold,role='development pilot; not full100 formal result'))
    def one(c,k):
        case=f'case_{c:03}';folder=a.output/f'{case}_{k}cores';old=ROOT/'图表/runs/20260924-A-q1-event-ranking-full100'/f'{case}_{k}cores_seed0_routes_gate_reuse'
        command=[sys.executable,str(ROOT/'程序/q1_timed_portfolio.py'),str(PROCESSED/'data'/f'{case}.json'),'-n',str(k),'--seconds',str(a.seconds),'--output',str(folder)]
        if not a.cold:command+=['--seed-plan',str(old/'plan.json')]
        with (a.output/f'{case}_{k}.log').open('w',encoding='utf-8') as log:
            proc=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT)
        run=json.loads((folder/'run.json').read_text(encoding='utf-8')) if (folder/'run.json').exists() else {'complete':False}
        search=json.loads((old/'search.json').read_text(encoding='utf-8'))
        base=min(x['makespan'] for x in search['evaluations']);after=run.get('selected',{}).get('makespan')
        row=dict(case=case,cores=k,complete=run['complete'],returncode=proc.returncode,before=base,after=after,wall_seconds=run.get('wall_seconds'),within_limit=run.get('within_limit'),mode='cold' if a.cold else 'warm',single=search['singlecore_makespan'])
        if after:row['reduction_pct']=100*(base-after)/base
        return row
    rows=[];start=time.monotonic()
    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        futures=[pool.submit(one,c,k) for c,k in jobs]
        for f in as_completed(futures):
            rows.append(f.result());write_json(a.output/'progress.json',rows);print(json.dumps(rows[-1]),flush=True)
    rows.sort(key=lambda r:(r['case'],r['cores']));write_json(a.output/'summary.json',dict(runs=rows,total_wall_seconds=time.monotonic()-start))

if __name__=='__main__':main()
