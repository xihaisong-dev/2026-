"""Attribute recorded r06 overhead without running new evaluator calls."""
import json
from collections import OrderedDict
from q1_io import ROOT,write_json

OUT=ROOT/'图表/runs/20260924-A-q2-overhead-r07'

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    totals={a:dict(seconds=0.,assessment_seconds=0.,residual_seconds=0.,calls=0,unique=0,repeated_calls=0) for a in ['routed','reserve']}
    rows=[]
    for p in sorted((ROOT/'图表/runs/20260924-A-q2-reserve-r06-v2/cases').glob('*/*/*/search.json')):
        s=json.loads(p.read_text());a=s['arm'];t=totals[a];seen=set();repeat=0
        for r in s['evaluations']:
            if not r['cache_hit'] and r['plan_sha256'] in seen:repeat+=1
            seen.add(r['plan_sha256'])
        assess=sum(r['seconds'] for r in s['evaluations'])
        row=dict(source=p.relative_to(ROOT).as_posix(),arm=a,seconds=s['solve_seconds'],assessment_seconds=assess,
                 residual_seconds=s['solve_seconds']-assess,calls=s['official_calls'],unique=len(seen),repeated_calls=repeat)
        rows.append(row)
        for k in t:t[k]+=row[k]
    write_json(OUT/'attribution.json',dict(totals=totals,rows=rows,note='Residual includes generation, J proposals and bookkeeping; not a direct generation profile.'))
    print(json.dumps(totals,indent=2))

if __name__=='__main__':main()
