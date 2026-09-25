import sys,json,time,zipfile,hashlib
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'程序'))
from q3_combination_campaign import check,job
from q2_timed_portfolio import atomic
out=root/'图表/runs/20260925-A-q3-combination-full100';cases=[19,26,10,94,6,65,11,93]
if __name__=='__main__':
 c=check(out);started=time.time()
 atomic(out/'local_execution.json',dict(cases=cases,host='Lenovo-local',workers=1,started=started,logical_cpus=32,available_memory_mib=2812,source_commit=c['source_commit']))
 for i in cases:
  row=job(out,c,dict(case=i,arm='combined'))
  print(json.dumps(dict(case=i,valid=row['valid'],makespan=row.get('selected_l2'),seconds=row.get('solve_seconds'))),flush=True)
  if not row['valid']:raise RuntimeError('Local shard validation failed')
 files=[out/'local_execution.json']
 for i in cases:
  name=f'case_{i:03}_combined';files += list((out/'jobs'/name).glob('*'));files += [out/'rows'/(name+'.json')]
 manifest={f.relative_to(root).as_posix():hashlib.sha256(f.read_bytes()).hexdigest() for f in files if f.is_file()}
 atomic(out/'local_export_manifest.json',dict(cases=cases,files=manifest,finished=time.time()))
 files.append(out/'local_export_manifest.json')
 with zipfile.ZipFile(root/'output/q3-local-shard.zip','w',zipfile.ZIP_DEFLATED) as z:
  for f in files:
   if f.is_file():z.write(f,f.relative_to(root).as_posix())
 print('LOCAL_SHARD_COMPLETE',flush=True)
