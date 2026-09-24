"""Verify r03 exports and unchanged baselines/parameter evidence locally."""
import argparse,json,gzip
from pathlib import Path
from q1_io import ROOT,PROCESSED,sha,write_json
from q3_solver import load,evaluate,audit,audit_cache

def main():
    p=argparse.ArgumentParser();p.add_argument('run',type=Path);a=p.parse_args()
    c=json.loads((a.run/'contract.json').read_text());done=json.loads((a.run/'completion.json').read_text());assert done['complete'] and done['count']==36
    for f,h in c['sources'].items():assert sha((ROOT/'程序'/f).read_bytes())==h
    freeze=json.loads((ROOT/'审查/证据/20260924-A-q3/baseline-freeze-r02.json').read_text(encoding='utf-8'))
    assert all(sha((ROOT/freeze['baseline']/f).read_bytes())==h for f,h in freeze['files'].items())
    params=json.loads((ROOT/'审查/证据/20260924-A-q3/parameter-freeze-before-r03.json').read_text(encoding='utf-8'))
    assert all(sha((ROOT/f).read_bytes())==h for f,h in params.items())
    count=0
    for f in a.run.glob('case_*/*/*/result.json.gz'):
        audit_cache(json.load(gzip.open(f,'rt',encoding='utf-8')));count+=1
    assert count==36
    settings,delay,cache,_=load();rows=[]
    for case,n,mode in [(9,5,'iterative'),(9,5,'unclassified_iterative'),(67,2,'iterative')]:
        folder=a.run/f'case_{case:03}/{n}/{mode}'
        raw=json.loads((PROCESSED/f'data/case_{case:03}.json').read_text(encoding='utf-8'));plan=json.loads((folder/'plan.json').read_text(encoding='utf-8'))
        r=evaluate(raw,plan,settings,delay,cache);saved=json.load(gzip.open(folder/'result.json.gz','rt',encoding='utf-8'))
        assert json.loads(json.dumps(r))==saved
        rows.append(dict(case=case,cores=n,mode=mode,makespan=r['makespan'],all_exported_fields_equal=True,checks=audit(raw,plan,r,settings,delay)))
    out=a.run/'local_verification.json';assert not out.exists()
    write_json(out,dict(fifo_ledgers=count,replays=rows,original_baseline_files_unchanged=len(freeze['files']),parameter_files_unchanged=len(params)))
    print('PASS: 36 FIFO ledgers, 3 complete cross-platform replays, baseline/parameter files unchanged')

if __name__=='__main__':main()
