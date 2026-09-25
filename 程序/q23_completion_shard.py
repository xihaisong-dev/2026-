"""Resume disjoint completion shards without changing the frozen worker."""
import argparse, concurrent.futures, json, os, platform, signal, subprocess, sys, time
from pathlib import Path
from q23_delivery_complete import read, sha
from q1_io import verify

def save(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp=p.with_suffix('.tmp'); tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8'); tmp.replace(p)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('root',type=Path);ap.add_argument('--owner',choices=['local','server'],required=True);ap.add_argument('--workers',type=int,required=True);ap.add_argument('--drain-parent',type=int)
    a=ap.parse_args();root=a.root;c=read(root/'contract.json');allocation=read(root/'allocation.json');verify()
    for p,h in c['files'].items():
        assert sha(p)==h,p
    # The old coordinator is stopped; already-started workers keep their results.
    if a.drain_parent:
        deadline=time.monotonic()+2600
        pending=allocation['old_started']
        while any(not (root/'jobs'/f'{j:04}'/'row.json').exists() for j in pending):
            if time.monotonic()>deadline:raise RuntimeError('Drain incomplete; inspect original workers before resuming')
            time.sleep(5)
        # Only this verified, stopped coordinator is terminated, not its workers.
        cmd=Path(f'/proc/{a.drain_parent}/cmdline').read_bytes()
        assert b'q23_delivery_complete.py' in cmd and str(root).encode() in cmd
        os.kill(a.drain_parent,signal.SIGKILL)
        for j in pending:
            dest=root/'rows'/f'{j:04}.json'
            if not dest.exists():
                r=read(root/'jobs'/f'{j:04}'/'row.json')
                r.update(recovered_from_worker_row=True,coordinator_exitcode_unavailable=True,host=platform.node())
                save(dest,r)
    def run(j):
        dest=root/'rows'/f'{j:04}.json'
        if dest.exists():return read(dest)
        out=root/'jobs'/f'{j:04}'
        if out.exists():raise RuntimeError(f'Existing unfinished job: {j}; manual reconciliation required')
        cmd=[sys.executable,str(Path(__file__).with_name('q23_delivery_complete.py')),str(root),'--worker',str(j)]
        t=time.monotonic();kw={'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {'start_new_session':True}
        p=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,**kw)
        timed_out=False
        try:stdout,stderr=p.communicate(timeout=2400)
        except subprocess.TimeoutExpired:
            timed_out=True
            if os.name=='nt':subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
            else:os.killpg(p.pid,signal.SIGKILL)
            stdout,stderr=p.communicate()
        r=read(out/'row.json') if (out/'row.json').exists() else dict(**c['jobs'][j],valid=False,error='worker_failed_or_timeout')
        r.update(command=cmd,returncode=p.returncode,wall=time.monotonic()-t,host=platform.node(),owner=a.owner,concurrency=a.workers,timed_out=timed_out,stdout=stdout.decode('utf-8','replace'),stderr=stderr.decode('utf-8','replace'))
        r['valid']=bool(r['valid'] and p.returncode==0 and not timed_out);save(dest,r);return r
    ids=allocation[a.owner];done=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as ex:
        fs=[ex.submit(run,j) for j in ids]
        for f in concurrent.futures.as_completed(fs):
            r=f.result();done.append(r)
            progress=dict(owner=a.owner,expected=len(ids),finished=len(done),valid=sum(x['valid'] for x in done),failures=[x for x in done if not x['valid']])
            save(root/f'progress-{a.owner}.json',progress);print(json.dumps({k:v for k,v in progress.items() if k!='failures'}),flush=True)
    save(root/f'complete-{a.owner}.json',progress)

if __name__=='__main__':main()
