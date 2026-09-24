"""Cross-platform verification of r02 and both parameter diagnostics."""
import argparse,gzip,json
from pathlib import Path
from q1_io import ROOT,PROCESSED,sha,write_json
from q3_solver import load,evaluate,audit,audit_cache

def main():
    p=argparse.ArgumentParser();p.add_argument('--pilot',type=Path,required=True);p.add_argument('--parameters',type=Path,nargs='+',required=True);a=p.parse_args()
    c=json.loads((a.pilot/'contract.json').read_text(encoding='utf-8'))
    for f,h in c['source_hashes'].items():assert sha((ROOT/'程序'/f).read_bytes())==h
    base=ROOT/'图表/runs/20260924-A-q3-full-r02'
    assert all(sha((base/f).read_bytes())==h for f,h in c['baseline_hashes'].items())
    ledgers=0
    for run in [a.pilot]+a.parameters:
        done=json.loads((run/'completion.json').read_text());assert done['complete']
        for f in run.rglob('*.json.gz'):
            audit_cache(json.load(gzip.open(f,'rt',encoding='utf-8')));ledgers+=1
    s,d,c,_=load();rows=[]
    targets=[(12,a.pilot/'case_012/5/window','result.json.gz',c),(67,a.pilot/'case_067/2/joint','result.json.gz',c)]
    c2=dict(c);c2['cache_capacity_bytes']=65536;c2['cache_bandwidth_bytes_per_cycle']=125
    targets.append((44,a.parameters[-1]/'case_044/65536_125','selected.json.gz',c2))
    for case,folder,name,cache in targets:
        raw=json.loads((PROCESSED/f'data/case_{case:03}.json').read_text(encoding='utf-8'));plan=json.loads((folder/'plan.json').read_text(encoding='utf-8'))
        old=json.load(gzip.open(folder/name,'rt',encoding='utf-8'));r=evaluate(raw,plan,s,d,cache)
        assert json.loads(json.dumps(r))==old
        rows.append(dict(case=case,makespan=r['makespan'],all_json_fields_equal=True,checks=audit(raw,plan,r,s,d)))
    assert ledgers==108
    out=a.pilot/'local_verification.json';assert not out.exists();write_json(out,dict(fifo_ledgers=ledgers,cross_platform_replays=rows,baseline_hashes_match=True))
    print('PASS',ledgers,'FIFO ledgers;',len(rows),'cross-platform full replays')

if __name__=='__main__':main()
