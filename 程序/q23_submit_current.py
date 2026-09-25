"""Explicit warm-start entry for the adopted Q2/Q3 combinations; Appendix B output."""
import argparse,json,time
from pathlib import Path
from q1_io import write_json,official
from q23_portfolio_reuse import run

def main():
 entry_started=time.monotonic()
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('graph',type=Path);p.add_argument('--problem',type=int,choices=[2,3],required=True);p.add_argument('-n','--cores',type=int,choices=range(2,6),required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--migration',type=Path);p.add_argument('--seed-plan',type=Path);p.add_argument('--anchor',type=Path);p.add_argument('--seconds',type=float,default=590);p.add_argument('--max-proposals',type=int,default=384);a=p.parse_args()
 seed=a.migration if a.problem==2 else a.seed_plan
 if seed is None:p.error('Q2 requires --migration; Q3 requires --seed-plan. Historical seed generation is excluded; no implicit case lookup.')
 official();from stub_multicore_cut_and_schedule import validate_multicore_plan
 raw=json.loads(a.graph.read_text(encoding='utf-8-sig'))
 for f in [seed,a.anchor] if a.problem==3 else [seed]:
  if f:
   plan=json.loads(f.read_text(encoding='utf-8-sig'));validate_multicore_plan(raw,plan)
   if len(plan['core_schedules'])!=a.cores:p.error('Initial plan core count differs from requested cores')
 args={k:str(v) if isinstance(v,Path) else v for k,v in vars(a).items()};args.update(seed=0,reuse=True,cache_mib=32);t=time.monotonic();s=run(args)
 if not(s['valid'] and s['complete'] and not s['error'] and not s['deadline_stop'] and s['worker_exitcode']==0):raise RuntimeError('No completely verified final solution; inspect summary.json')
 plan=json.loads((a.output/s['plan']).read_text(encoding='utf-8'));validate_multicore_plan(raw,plan)
 target=a.output/(a.graph.stem+'_multicore_res.json');write_json(target,plan)
 write_json(a.output/'delivery.json',dict(solution=target.name,elapsed_including_export=time.monotonic()-entry_started,solver_summary='summary.json',seed_generation_included=False,algorithm='protected' if a.problem==2 else 'combined',generation_reuse=True))
 print(target)
if __name__=='__main__':main()
