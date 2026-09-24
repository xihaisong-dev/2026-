"""Verify complete coverage, inherited B scores, cache ledgers, and selected plans."""
import argparse,csv,gzip,json,statistics
from pathlib import Path
from q1_io import ROOT,PROCESSED,sha,write_json
from q2_evaluator import key
from q3_solver import load,audit_cache,audit


def readgz(p):
    with gzip.open(p,'rt',encoding='utf-8') as f:return json.load(f)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    assert not a.output.exists()
    rows=json.loads((a.run/'progress.json').read_text(encoding='utf-8'))
    assert {(r['case'],r['cores']) for r in rows}=={(i,n) for i in range(1,101) for n in range(1,6)} and len(rows)==500
    reference={ (int(r['case']),int(r['cores'])):r for r in csv.DictReader((ROOT/'图表/runs/20260924-A-q2-delivery-r07/selected_500_rows.csv').open(encoding='utf-8-sig')) }
    s,d,_,_=load();checks=[];extra_memory=0
    for row in rows:
        i,n=row['case'],row['cores'];folder=a.run/f'case_{i:03}/{n}'
        old=reference[i,n];assert row['no_l2']==int(old['makespan']) and row['no_l2_added']==int(old['added_copy_bytes'])
        rawpath=PROCESSED/f'data/case_{i:03}.json';assert row['input_sha256']==sha(rawpath.read_bytes())
        seedpath=ROOT/f'图表/runs/20260924-A-q2-delivery-r07/solutions/{n}cores/case_{i:03}_multicore_res.json'
        assert row['seed_sha256']==sha(seedpath.read_bytes())
        search=json.loads((folder/'search.json').read_text());plan=json.loads((folder/f'case_{i:03}_multicore_res.json').read_text())
        assert key(plan)==search['selected_plan_sha256'] and search['replay_equal']
        fixed=readgz(folder/'fixed_l2.json.gz');selected=readgz(folder/'selected_l2.json.gz');no=readgz(folder/'no_l2.json.gz')
        assert (selected['makespan'],selected['data_movement_bytes']['added_copy_bytes']) <= (fixed['makespan'],fixed['data_movement_bytes']['added_copy_bytes'])
        assert no['makespan']==row['no_l2'] and no['data_movement_bytes']==fixed['data_movement_bytes']
        ac=audit_cache(fixed);bc=audit_cache(selected)
        assert selected['makespan']==row['selected_l2'] and fixed['makespan']==row['fixed_l2']
        assert selected['cache_stats']['hit_rate']==row['selected_hit_rate']
        if search['selected_plan_sha256']!=search['seed_plan_sha256']:
            raw=json.loads(rawpath.read_text());seed=json.loads(seedpath.read_text())
            audit(raw,seed,fixed,s,d);extra_memory+=1
        checks.append(dict(case=i,cores=n,passed=True,selected_sha256=sha((folder/f'case_{i:03}_multicore_res.json').read_bytes()),fixed_ddr=ac['physical_ddr_bytes_derived'],selected_ddr=bc['physical_ddr_bytes_derived']))
    write_json(a.output,dict(passed=True,count=500,unchanged_q2_baselines=500,cache_ledgers=1000,
                selected_global_memory_audits=500,additional_changed_anchor_memory_audits=extra_memory,checks=checks))
    print('PASS 500 paired configurations')


if __name__=='__main__':main()
