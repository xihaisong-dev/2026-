import csv,gzip,json,statistics,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'程序'))
from q1_io import sha,write_json,verify
from q2_full_campaign import OUT,read

verify();c=read(OUT/'contract.json')
assert all(sha((ROOT/'程序'/n).read_bytes())==h for n,h in c['sources'].items())
assert all(sha((ROOT/p).read_bytes())==h for p,h in c['plans'].items())
for p,h in read(OUT/'delivery/manifest.json')['files'].items():assert sha((ROOT/p).read_bytes())==h
with (OUT/'delivery/selected_500_rows.csv').open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
assert len(rows)==500 and {(int(r['case']),int(r['cores'])) for r in rows}=={(i,k) for i in range(1,101) for k in range(1,6)}
s=read(OUT/'summary.json')
for k in range(1,6):assert abs(statistics.mean(float(r['speedup']) for r in rows if int(r['cores'])==k)-s['curves']['routed'][str(k)])<1e-12
assert len(list((OUT/'delivery/solutions').glob('*/*.json')))==400
checks=[]
for i,k,relative in [(1,2,'output/q2-r05-cold-reproduction'),(2,5,'output/q2-r05-portable/trial-002-5'),(1,1,'output/q2-r05-portable/trial-001-1')]:
    folder=ROOT/relative
    with gzip.open(folder/'evaluation.json.gz','rt',encoding='utf-8') as f:actual=json.load(f)
    expected=OUT/f'cases/case_{i:03}/fixed_single.json.gz' if k==1 else OUT/f'cases/case_{i:03}/{k}/routed/evaluation.json.gz'
    with gzip.open(expected,'rt',encoding='utf-8') as f:assert actual==json.load(f)
    if k>1:
        assert read(folder/f'case_{i:03}_multicore_res.json')==read(expected.parent/f'case_{i:03}_multicore_res.json')
    stats=read(folder/'search.json');meta=read(folder/'run.json')
    checks.append(dict(case=i,cores=k,folder=relative,full_result_equal=True,
                       official_B_search_calls=stats.get('official_calls',0),B_final_replays=int(k>1),
                       migration_source=meta['migration_source'],elapsed_seconds=meta['elapsed_seconds']))
qa=read(ROOT/'图表/visual_qa.json');assert qa['critical_count']==qa['warning_count']==0
assert not subprocess.check_output(['git','diff','--name-only','HEAD','--','程序/q1_*.py','图表/runs/20260924-A-q1-delivery-r02'],cwd=ROOT,text=True).strip()
dest=Path(__file__).parent/'final_checks.json';assert not dest.exists()
write_json(dest,dict(status='PASS_COMPUTATIONAL_DELIVERY_CHECKS',rows=500,plans=400,
                     source_input_migration_hashes=True,reproductions=checks,
                     extra_seed_checks='case001/2 seed-only and cold entry each use 12 A opportunities, outside all B comparisons',
                     visual_critical=0,visual_warnings=0,formal_manuscript_acceptance=False,
                     package_archive=read(ROOT/'output/q2-r05-portable.archive.json'),
                     q1_frozen_code_and_scores_unchanged=True))
print(json.dumps(checks,ensure_ascii=False))
