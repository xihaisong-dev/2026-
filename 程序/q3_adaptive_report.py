"""Check the predeclared adaptive promotion rule and iteration invariants."""
import argparse,json,statistics
from pathlib import Path
from q1_io import write_json

def main():
    p=argparse.ArgumentParser();p.add_argument('run',type=Path);a=p.parse_args()
    c=json.loads((a.run/'contract.json').read_text());done=json.loads((a.run/'completion.json').read_text());rows=json.loads((a.run/'progress.json').read_text())
    assert done['complete'] and done['count']==36 and done['baseline_unchanged']
    assert {(r['case'],r['cores'],r['mode']) for r in rows}=={(i,n,m) for i,n in c['discovery']+c['validation'] for m in c['modes']}
    summary={}
    for mode in c['modes']:
        summary[mode]={}
        for part in ['discovery','validation']:
            xs=[r for r in rows if r['mode']==mode and [r['case'],r['cores']] in c[part]]
            summary[mode][part]=dict(wins=sum(r['ratio']>1 for r in xs),mean_ratio=statistics.mean(r['ratio'] for r in xs),mean_reduction=statistics.mean(1-1/r['ratio'] for r in xs),calls=sum(r['calls'] for r in xs),diagnoses=sum(r['diagnoses'] for r in xs),seconds=sum(r['seconds'] for r in xs))
    for r in rows:
        search=json.loads((a.run/f"case_{r['case']:03}/{r['cores']}/{r['mode']}/search.json").read_text())
        assert search['replay_equal'] and search['checks']['cache']['fifo_ledger']
        assert len(search['evaluations'])<=24 and len({e['plan_sha256'] for e in search['evaluations']})==len(search['evaluations'])
        for i,rr in enumerate(search['rounds']):
            assert sum(rr['classification']['cycles'].values())==rr['before']
            assert rr.get('after',rr['before'])<=rr['before']
            if i:assert rr['seed']==search['rounds'][i-1]['selected'] and search['rounds'][i-1]['accepted']
    comparisons={}
    for part in ['discovery','validation']:
        comparisons[part]={}
        for control in ['single','unclassified_iterative']:
            pairs=[{r['mode']:r for r in rows if r['case']==i and r['cores']==n} for i,n in c[part]]
            comparisons[part][control]=dict(wins=sum(x['iterative']['makespan']<x[control]['makespan'] for x in pairs),ties=sum(x['iterative']['makespan']==x[control]['makespan'] for x in pairs),losses=sum(x['iterative']['makespan']>x[control]['makespan'] for x in pairs))
    d,v=summary['iterative']['discovery'],summary['iterative']['validation']
    passed=d['wins']>=3 and d['mean_ratio']>=1.005 and v['wins']>=3 and v['mean_ratio']>=1.002 and all(v['mean_ratio']>summary[x]['validation']['mean_ratio'] for x in ['single','unclassified_iterative']) and comparisons['validation']['single']['wins']>=2
    out=dict(summary=summary,comparisons=comparisons,promote=passed,audited=36,candidate_calls=sum(r['calls'] for r in rows),invalid=sum(r['invalid'] for r in rows),baseline_unchanged=True)
    dest=a.run/'summary.json';assert not dest.exists();write_json(dest,out);print(json.dumps(out,indent=2))

if __name__=='__main__':main()
