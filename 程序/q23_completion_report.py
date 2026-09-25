"""Build complete 1-5 core tables only after all required official rows pass."""
import argparse,csv,json
from pathlib import Path
from q1_io import write_json

def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def report(root,previous):
 rows=[read(p) for p in (root/'rows').glob('*.json')];old=[read(p) for p in (previous/'rows').glob('*.json')];data={2:{},3:{}};errors=[]
 for x in old:
  if x['problem']==2 and x['valid']:data[2][(x['case'],5)]={**x,'cores':5,'cache_hit_rate':None}
 for x in rows:
  if not x['valid']:errors.append([x['problem'],x['case'],x['cores'],x.get('error')]);continue
  k=(x['case'],x['cores']);q=x['problem']
  if k in data[q]:errors.append(['duplicate',q,k])
  data[q][k]=x
 missing={str(q):[(n,k) for k in range(1,6) for n in range(1,101) if (n,k) not in data[q]] for q in [2,3]}
 result=dict(finished=len(rows),expected=900,errors=errors,missing=missing,complete=not errors and not any(missing.values()),submit_ready=False)
 if result['complete']:
  points=[]
  for q in [2,3]:
   fields=['case','cores','makespan','added','single']+(['no_l2_makespan','no_l2_added','cache_hit_rate','same_plan_cache_ratio'] if q==3 else [])
   with (root/f'q{q}_appendix.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(data[q][k] for k in sorted(data[q],key=lambda k:(k[1],k[0])))
   for k in range(1,6):
    xs=[data[q][(n,k)] for n in range(1,101)];p=dict(problem=q,cores=k,cases=100,mean_speedup=sum(x['single']/x['makespan'] for x in xs)/100,total_cycles=sum(x['makespan'] for x in xs),added_bytes=sum(x['added'] for x in xs))
    if q==3:p.update(mean_same_plan_cache_ratio=sum(x['no_l2_makespan']/x['makespan'] for x in xs)/100,no_l2_total_cycles=sum(x['no_l2_makespan'] for x in xs),mean_case_hit_rate=sum(x['cache_hit_rate'] for x in xs)/100)
    points.append(p)
  result['points']=points
 write_json(root/'delivery_report.json',result);return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--previous',type=Path,default=Path('图表/runs/20260925-A-q23-full100-verified'));a=p.parse_args();r=report(a.root,a.previous);print(json.dumps({k:v for k,v in r.items() if k!='missing'}));
 if not r['complete']:raise SystemExit(2)
