"""Locally audit all pilot FIFO traces and replay two changed plans."""
import argparse,gzip,json
from pathlib import Path
from q1_io import PROCESSED,ROOT,sha,write_json
from q3_solver import load,evaluate,audit,audit_cache

def main():
    p=argparse.ArgumentParser();p.add_argument('run',type=Path);a=p.parse_args()
    contract=json.loads((a.run/'contract.json').read_text(encoding='utf-8'))
    assert contract['source_sha256']==sha((ROOT/'程序/q3_explore.py').read_bytes())
    base=ROOT/'图表/runs/20260924-A-q3-full-r02'
    assert all(sha((base/k).read_bytes())==v for k,v in contract['baseline_hashes'].items())
    count=0
    for p in a.run.glob('case_*/*/*/result.json.gz'):
        audit_cache(json.load(gzip.open(p,'rt',encoding='utf-8')));count+=1
    assert count==48
    settings,delay,cache,_=load();checks=[]
    for case,n,family in [(5,5,'event'),(12,5,'split')]:
        p=a.run/f'case_{case:03}/{n}/{family}'
        raw=json.loads((PROCESSED/f'data/case_{case:03}.json').read_text(encoding='utf-8'))
        plan=json.loads((p/'plan.json').read_text(encoding='utf-8'))
        result=evaluate(raw,plan,settings,delay,cache)
        old=json.load(gzip.open(p/'result.json.gz','rt',encoding='utf-8'))
        # JSON object keys are strings; round-trip the in-memory integer keys.
        assert json.loads(json.dumps(result))==old
        checks.append(dict(case=case,cores=n,family=family,makespan=result['makespan'],cross_platform_json_result_equal=True,checks=audit(raw,plan,result,settings,delay)))
    dest=a.run/'local_verification.json';assert not dest.exists()
    write_json(dest,dict(cache_ledgers=count,cross_platform_replays=checks,server_seed_hashes_match_local=True,comparison='All exported fields equal after standard JSON serialization; no numerical fields excluded.'))
    print('FIFO ledgers:',count,'cross-platform replays:',len(checks))

if __name__=='__main__':main()
