"""Extract r07 delivery and test cold, seeded, batch and official CLI reproduction."""
import gzip, hashlib, json, os, subprocess, sys, time, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / '审查/证据/20260924-A-q2-delivery-r07'
RUN = ROOT / '图表/runs/20260924-A-q2-full-r07-shared-r08'

def read(p):
    if p.suffix == '.gz':
        with gzip.open(p, 'rt', encoding='utf-8') as f: return json.load(f)
    return json.loads(p.read_text(encoding='utf-8-sig'))

def main():
    dest = ROOT / '_tmp/q2-r07-extracted-check'
    assert not dest.exists()
    dest.mkdir(parents=True)
    archive = ROOT / 'output/q2-r07-portable.zip'
    with zipfile.ZipFile(archive) as z: z.extractall(dest)
    base = dest / 'q2-r07-portable'
    records = []
    def command(label, args):
        start=time.perf_counter()
        p=subprocess.run([sys.executable]+args,cwd=base,capture_output=True,env=dict(os.environ,PYTHONUTF8='1',PYTHONIOENCODING='utf-8'))
        (EVIDENCE/(label+'.log.txt')).write_bytes(p.stdout+p.stderr)
        records.append(dict(label=label,command=['python']+args,working_directory='extracted q2-r07-portable',returncode=p.returncode,seconds=time.perf_counter()-start))
        assert p.returncode == 0, (label, p.stderr.decode('utf-8',errors='replace'))
        print(label, 'PASS', flush=True)
    command('manifest', ['verify_package.py'])
    command('batch-single', ['程序/q2_r07_reproduce.py','--cases','1','--cores','1','--workers','1','--output','batch-single'])
    command('cold-001-2', ['程序/q2_current_submit.py','数据/processed/q1/data/case_001.json','-n','2','--output','cold-001-2'])
    command('seeded-005-5', ['程序/q2_current_submit.py','数据/processed/q1/data/case_005.json','-n','5','--migration','图表/runs/20260924-A-q1-delivery-r02/solutions/5cores/case_005_multicore_res.json','--output','seeded-005-5'])
    checks=[]
    for i,k,rel in [(1,1,'batch-single/case_001/1'),(1,2,'cold-001-2'),(5,5,'seeded-005-5')]:
        actual=base/rel
        expected_plan=ROOT/f'图表/runs/20260924-A-q2-delivery-r07/solutions/{k}cores/case_{i:03}_multicore_res.json'
        assert read(actual/f'case_{i:03}_multicore_res.json')==read(expected_plan)
        result=read(actual/'evaluation.json.gz')
        if k==1:
            reference=read(RUN/f'cases/case_{i:03}/single.json')
            assert result['makespan']==reference['makespan']
            assert result['data_movement_bytes']['added_copy_bytes']==reference['added_copy_bytes']
        else:
            assert result==read(RUN/f'cases/case_{i:03}/{k}/fast/evaluation.json.gz')
            assert read(actual/'search.json')['slots']==12
        checks.append(dict(case=i,cores=k,plan_equal=True,full_official_result_equal=k>1,single_metrics_equal=k==1))
    out=base/'direct-official';out.mkdir()
    command('official-cli', ['数据/processed/q1/code/multicore_cut_evaluate_problem_2.py','数据/processed/q1/data/case_005.json','seeded-005-5/case_005_multicore_res.json','--config','数据/processed/q1/data/config.txt','-o','direct-official/result.json','--trace-output','direct-official/trace.json','--log-output','direct-official/log.txt'])
    actual=read(out/'result.json');actual.pop('input_graph');actual.pop('input_plan')
    assert actual==read(base/'seeded-005-5/evaluation.json.gz')
    for rel in ['cold-001-2','seeded-005-5','batch-single/case_001/1']:
        for name in ['run.json','search.json']:
            (EVIDENCE/(rel.replace('/','-')+'-'+name)).write_bytes((base/rel/name).read_bytes())
    report=dict(status='PASS',scope='portable package sampled reproducibility; full100 evidence audited separately',python=sys.version,archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),commands=records,checks=checks,direct_official_full_result_equal=True,resource_snapshot=read(base/'batch-single/execution.json')['resources'])
    (EVIDENCE/'reproduction.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('ALL PASS',flush=True)

if __name__=='__main__': main()
