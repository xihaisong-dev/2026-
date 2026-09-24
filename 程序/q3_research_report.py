"""Evaluate frozen r02 promotion criteria and summarize parameter adaptation."""
import argparse,json,statistics
from pathlib import Path
from q1_io import write_json

def main():
    p=argparse.ArgumentParser();p.add_argument('run',type=Path);a=p.parse_args()
    c=json.loads((a.run/'contract.json').read_text(encoding='utf-8'));done=json.loads((a.run/'completion.json').read_text())
    assert done['complete'] and done['count']==36 and done['baseline_unchanged']
    rows=json.loads((a.run/'progress.json').read_text());assert len({(r['case'],r['cores'],r['family']) for r in rows})==36
    summary={}
    for family in c['families']:
        summary[family]={}
        for part in ['discovery','validation']:
            xs=[r for r in rows if r['family']==family and [r['case'],r['cores']] in c[part]];assert len(xs)==6
            summary[family][part]=dict(wins=sum(r['ratio']>1 for r in xs),mean_ratio=statistics.mean(r['ratio'] for r in xs),mean_time_reduction=statistics.mean(1-r['makespan']/r['baseline'] for r in xs),calls=sum(r['candidate_calls'] for r in xs))
    promoted=[]
    for family in ['window','joint']:
        d,v=summary[family]['discovery'],summary[family]['validation']
        if d['wins']>=3 and d['mean_ratio']>=1.005 and v['wins']>=3 and v['mean_ratio']>=1.002 and v['mean_ratio']>summary['control']['validation']['mean_ratio']:promoted.append(family)
    for r in rows:
        s=json.loads((a.run/f"case_{r['case']:03}/{r['cores']}/{r['family']}/search.json").read_text())
        assert s['replay_equal'] and s['checks']['cache']['fifo_ledger'] and r['makespan']<=r['baseline']
    out=dict(families=summary,promoted=promoted,audited=36,candidate_calls=sum(r['candidate_calls'] for r in rows),invalid=sum(r['invalid'] for r in rows),baseline_unchanged=True)
    dest=a.run/'summary.json';assert not dest.exists();write_json(dest,out);print(json.dumps(out,indent=2))

if __name__=='__main__':main()
