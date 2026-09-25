"""One-shot authorized batch collector; password is read interactively, never saved.

Wait for both disjoint shards and cold audits, then refresh and compile materials.
No scheduling service, no remote process termination, no algorithm modifications.
"""
import argparse,base64,getpass,hashlib,json,os,subprocess,sys,time,zipfile
from pathlib import Path
sys.path.insert(0,str(Path('_tmp/ssh-deps').resolve()))
import paramiko
from q23_completion_shard import save

REMOTE='/home/xihs/q1-campaigns/20260925-q23-requirements-completion'
REL='图表/runs/20260925-A-q23-requirements-completion'
COLD='图表/runs/20260926-A-q123-cold-audit'

def main():
    a=argparse.ArgumentParser();a.add_argument('--paper-python',required=True);args=a.parse_args()
    client=paramiko.SSHClient();client.load_system_host_keys();client.connect('120.27.220.233',port=9022,username='xihs',password=getpass.getpass('SSH password (not saved): '),look_for_keys=False,allow_agent=False,timeout=20)
    client.get_transport().set_keepalive(30)
    allocation=json.loads((Path(REL)/'allocation.json').read_text('utf-8-sig'));allowed=set(allocation['server']+allocation['old_started']);seen=set();cold_done=False
    def remote(code):
        command="cd '"+REMOTE+"' && /home/xihs/q1-runtime/run-python -c \"import base64;exec(base64.b64decode('"+base64.b64encode(code.encode()).decode()+"'))\""
        _,out,err=client.exec_command(command,timeout=300);b=out.read();e=err.read();rc=out.channel.recv_exit_status()
        if rc:raise RuntimeError(e.decode('utf-8','replace'))
        return json.loads(b)
    while True:
        state=remote(f"from pathlib import Path\nimport json\np=Path({REL!r})\nprint(json.dumps(dict(rows=[int(x.stem) for x in (p/'rows').glob('*.json')],cold=Path({COLD!r},'complete.json').exists())))")
        todo=sorted(set(state['rows'])&allowed-seen)
        pull_cold=state['cold'] and not cold_done
        if todo or pull_cold:
            code=f'''from pathlib import Path
import json,zipfile,hashlib,time
root=Path({REL!r}); files=[]
for i in {todo!r}:
 d=root/'jobs'/f'{{i:04}}'
 files.append(root/'rows'/f'{{i:04}}.json')
 for n in ['row.json','evaluation.json.gz','same_plan_no_l2.json.gz','solver_summary.json']:
  if (d/n).exists():files.append(d/n)
 files.extend(d.glob('case_*_multicore_res.json'))
 for n in ['details.json','summary.json','verified.json','search/search.json','search/identity.json']:
  if (d/'solve'/n).exists():files.append(d/'solve'/n)
if {pull_cold!r}:
 files.extend(p for p in Path({COLD!r}).rglob('*') if p.is_file())
z=Path('_sync');z.mkdir(exist_ok=True);z=z/f'batch-{{time.time_ns()}}.zip'
with zipfile.ZipFile(z,'w',zipfile.ZIP_DEFLATED) as f:
 for p in files:f.write(p,p.as_posix())
print(json.dumps(dict(path=z.as_posix(),sha256=hashlib.sha256(z.read_bytes()).hexdigest(),files=len(files))))
'''
            bundle=remote(code);local=Path('output')/Path(bundle['path']).name;sftp=client.open_sftp();sftp.get(REMOTE+'/'+bundle['path'],str(local));sftp.close()
            assert hashlib.sha256(local.read_bytes()).hexdigest()==bundle['sha256']
            with zipfile.ZipFile(local) as z:
                for name in z.namelist():
                    dest=(Path.cwd()/name).resolve();assert dest.is_relative_to(Path.cwd().resolve())
                    assert name.startswith(REL+'/') or name.startswith(COLD+'/')
                    # Only transferred server-owned jobs may update the shared matrix.
                    if name.startswith(REL+'/jobs/') or name.startswith(REL+'/rows/'):
                        component=name[len(REL)+1:].split('/')[1];assert int(component.split('.')[0]) in allowed
                    dest.parent.mkdir(parents=True,exist_ok=True);data=z.read(name)
                    if dest.exists():assert dest.read_bytes()==data,f'Conflicting evidence: {name}'
                    else:dest.write_bytes(data)
            seen.update(todo);cold_done|=pull_cold
        rows=list((Path(REL)/'rows').glob('*.json'));valid=sum(json.loads(p.read_text('utf-8-sig'))['valid'] for p in rows)
        status=dict(finished=len(rows),valid=valid,expected=900,cold_complete=cold_done,server_collected=len(seen),timestamp=time.time(),material_status='waiting_for_complete_evidence')
        save(Path(REL)/'combined-progress.json',status);print(json.dumps(status),flush=True)
        if len(rows)==900 and cold_done:
            if valid!=900:raise RuntimeError('Some jobs invalid; repair before publishing')
            proc=subprocess.run([args.paper_python,'-X','utf8','程序/q123_complete_materials.py','--compile'],capture_output=True)
            Path('output/q123-publish.log').write_bytes(proc.stdout+proc.stderr)
            status.update(material_exitcode=proc.returncode,material_status='built_requires_visual_review' if proc.returncode==0 else 'build_failed_inspect_log')
            save(Path(REL)/'combined-progress.json',status)
            if proc.returncode:raise RuntimeError('Material build failed; output/q123-publish.log')
            return
        time.sleep(60)

if __name__=='__main__':main()
