"""Explicit post-hoc diagnostic: add capacity-sensitive cases after saturation."""
import argparse,json
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
from q1_io import ROOT,sha,write_json
from q3_parameter_reopt import job

def main():
    p=argparse.ArgumentParser();p.add_argument('--baseline',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--workers',type=int,default=4);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    pairs=[(44,1,c,b) for c in [65536,524288,1048576] for b in [125,250,500]]+[(67,2,c,b) for c in [524288,1048576,2097152] for b in [125,250,500]]
    write_json(a.output/'contract.json',dict(pairs=pairs,budget=8,scope='Post-hoc capacity diagnostics: first grid cases5/12 saturated for tested capacities; case44 known capacity-sensitive from prior sensitivity study, case67 selected for joint migration improvement. Not held-out validation.',sources={x:sha((ROOT/'程序'/x).read_bytes()) for x in ['q3_parameter_followup.py','q3_parameter_reopt.py','q3_cache_search.py']}))
    rows=[];errors=[]
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        fs={pool.submit(job,(*x,str(a.baseline),str(a.output))):x for x in pairs}
        for f in as_completed(fs):
            try:row=f.result();rows.append(row);print(json.dumps(row),flush=True)
            except Exception as exc:errors.append(dict(job=fs[f],error=repr(exc)))
            write_json(a.output/'progress.json',rows);write_json(a.output/'errors.json',errors)
    write_json(a.output/'completion.json',dict(complete=not errors,count=len(rows),errors=errors))
    if errors:raise RuntimeError(errors)

if __name__=='__main__':main()
