"""Export adopted plans with Appendix B names and unchanged plan semantics."""
import argparse,csv,gzip,hashlib,json
from pathlib import Path
from q1_io import official,write_json,verify

def export(out):
 verify();official()
 from stub_multicore_cut_and_schedule import validate_multicore_plan
 out.mkdir(parents=True,exist_ok=False);rows=[]
 for q in [1,2,3]:
  for k in (range(1,6) if q==1 else [5]):
   for n in range(1,101):
    graph=Path(f'数据/processed/q1/data/case_{n:03}.json');raw=json.loads(graph.read_text(encoding='utf-8'))
    if q==1:source=Path(f'图表/runs/20260924-A-q1-delivery-r02/solutions/{k}cores/case_{n:03}_multicore_res.json')
    else:source=Path(f'图表/runs/20260925-A-q23-full100-verified/jobs/q{q}_{n:03}/final.plan.json')
    p=json.loads(source.read_text(encoding='utf-8'));validate_multicore_plan(raw,p);assert len(p['core_schedules'])==k and set(p)=={'node_to_subgraph','core_schedules'}
    target=out/f'q{q}'/f'{k}cores'/f'case_{n:03}_multicore_res.json';target.parent.mkdir(parents=True,exist_ok=True);write_json(target,p)
    row=dict(problem=q,cores=k,case=n,source=source.as_posix(),output=target.as_posix(),source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),output_sha256=hashlib.sha256(target.read_bytes()).hexdigest())
    if q>1:
     with gzip.open(source.parent/'final.evaluation.json.gz','rt',encoding='utf-8') as f:e=json.load(f)
     row.update(makespan=e['makespan'],added_copy_bytes=e['data_movement_bytes']['added_copy_bytes'],cache_hit_rate=e.get('cache_stats',{}).get('hit_rate'))
    rows.append(row)
 write_json(out/'export_manifest.json',dict(count=len(rows),official_format_valid=True,rows=rows,complete_submission=False,pending='Latest Q2/Q3 low-core and Q3 same-plan no-L2 tables running separately'))
 return rows
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();print('exported',len(export(a.output)))
