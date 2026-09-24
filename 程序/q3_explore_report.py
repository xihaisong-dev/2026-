"""Summarize predeclared Q3 pilot; never promote on a post-hoc winner portfolio."""
import argparse,json,statistics
from pathlib import Path
from q1_io import write_json
from q3_explore import FAMILIES

def main():
    p=argparse.ArgumentParser();p.add_argument('run',type=Path);a=p.parse_args()
    contract=json.loads((a.run/'contract.json').read_text(encoding='utf-8'))
    done=json.loads((a.run/'completion.json').read_text(encoding='utf-8'))
    assert done['complete'] and done['count']==12 and done['baseline_unchanged']
    rows=json.loads((a.run/'progress.json').read_text(encoding='utf-8'))
    assert {(r['case'],r['cores']) for r in rows}=={tuple(x) for x in contract['discovery']+contract['validation']}
    report={};promoted=[]
    for family in FAMILIES:
        report[family]={}
        for part in ['discovery','validation']:
            selected=[r for r in rows if [r['case'],r['cores']] in contract[part]]
            ratios=[r['families'][family]['ratio'] for r in selected]
            report[family][part]=dict(count=len(selected),wins=sum(x>1 for x in ratios),losses=sum(x<1 for x in ratios),mean_ratio=statistics.mean(ratios),candidate_calls=sum(r['families'][family]['candidate_calls'] for r in selected),strict_wins_vs_ordinary=sum(r['families'][family]['makespan']<r['families']['ordinary']['makespan'] for r in selected))
        d,v=report[family]['discovery'],report[family]['validation']
        if family!='ordinary' and d['wins']>=3 and d['mean_ratio']>=1.005 and v['wins']>=2 and v['mean_ratio']>=1.002:promoted.append(family)
    checked=0
    for r in rows:
        for family in FAMILIES:
            s=json.loads((a.run/f"case_{r['case']:03}/{r['cores']}/{family}/search.json").read_text(encoding='utf-8'))
            assert s['checks']['cache']['fifo_ledger'] and s['checks']['synchronization'] and s['checks']['traffic_identity']
            assert s['makespan']<=r['baseline'];checked+=1
    out=dict(families=report,promoted=promoted,official_replay_and_audit_count=checked,baseline_unchanged=True,scope='Predeclared pilot only; validation is case holdout for new methods, not an unseen source dataset. Candidate counts are caps; structurally distinct moves may be exhausted.',invalid_candidates=sum('error' in e for f in a.run.glob('case_*/*/*/search.json') for e in json.loads(f.read_text(encoding='utf-8'))['evaluations']))
    dest=a.run/'summary.json';assert not dest.exists();write_json(dest,out)
    print(json.dumps(out,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
