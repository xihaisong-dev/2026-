"""Sequential fresh Q1 timing and strict comparison with prior cold outputs."""
import argparse
import gzip
import json
import platform
import subprocess
import sys
import time
from pathlib import Path
from q1_io import ROOT,write_json,sha


def read(p):return json.loads(Path(p).read_text('utf-8'))


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False);rows=[]
    for n in (72,76):
        base=a.output/f'case_{n:03}';base.mkdir()
        cmd=[sys.executable,str(ROOT/'程序/q1_submit.py'),str(ROOT/f'数据/processed/q1/data/case_{n:03}.json'),'-n','5','--output',str(base/'q1'),'--verify-final','--final-check-backend','counter']
        started=time.monotonic()
        with (base/'q1.log').open('wb') as f:proc=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT)
        elapsed=time.monotonic()-started
        row=dict(case=n,cores=5,command=cmd,returncode=proc.returncode,wall_seconds=elapsed,host=platform.node(),within_600_seconds=elapsed<=600,original_official_replayed=False)
        if proc.returncode==0:
            old=ROOT/f'图表/runs/20260926-A-q123-cold-audit/case_{n:03}/5/q1';new=base/'q1'
            row['plan_equal']=read(old/f'case_{n:03}_multicore_res.json')==read(new/f'case_{n:03}_multicore_res.json')
            row['full_result_equal']=json.loads(gzip.decompress((old/'evaluation.json.gz').read_bytes()))==json.loads(gzip.decompress((new/'evaluation.json.gz').read_bytes()))
            old_stats=read(old/'search.json');new_stats=read(new/'search.json')
            keys=('candidate','makespan','added_copy_bytes','best_makespan')
            row['evaluation_sequence_equal']=[{k:r[k] for k in keys} for r in old_stats['evaluations']]==[{k:r[k] for k in keys} for r in new_stats['evaluations']]
            row['proposal_ledger_equal']=old_stats['proposal_ledger']==new_stats['proposal_ledger']
            row['plan_sha256']=sha((new/f'case_{n:03}_multicore_res.json').read_bytes())
            row['run']=read(new/'run.json')
        write_json(base/'timing.json',row);rows.append(row);print(json.dumps({k:v for k,v in row.items() if k not in ('run','command')}),flush=True)
    write_json(a.output/'summary.json',dict(rows=rows,scope='sequential fresh processes; no historical initial plans or solver cache; OS page cache not flushed'))
    if not all(r.get('plan_equal') and r.get('full_result_equal') and r.get('evaluation_sequence_equal') and r.get('proposal_ledger_equal') for r in rows):raise SystemExit(1)


if __name__=='__main__':main()
