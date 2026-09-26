"""Verify downloaded Allin2 archive without rerunning optimization."""
from pathlib import Path
import csv
import hashlib
import io
import json
import math
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output/allin2-q1-complete-20260926'
sha = lambda b: hashlib.sha256(b).hexdigest()
completion = json.loads((OUT / 'delivery_complete.json').read_text())
archive = OUT / 'submission_q1.zip'
assert completion['status'] == 'verified'
assert sha(archive.read_bytes()) == completion['sha256']
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    prefix = 'submission_q1/'
    read = lambda n: z.read(prefix + n)
    manifest = json.loads(read('manifest.json'))
    for name, digest in manifest.items():
        assert sha(read(name)) == digest, name
    rows = list(csv.DictReader(io.StringIO(read('all_case_results.csv').decode('utf-8-sig'))))
    expected = {(f'case_{i:03d}', k) for i in range(1, 101) for k in range(1, 6)}
    assert len(rows) == 500
    assert {(r['case'], int(r['cores'])) for r in rows} == expected
    plans = [n for n in z.namelist() if '/solutions/' in n and n.endswith('_multicore_res.json')]
    assert len(plans) == 500
    for r in rows:
        assert sha(read(r['plan_path'])) == r['plan_sha256']
        assert math.isclose(float(r['speedup']), int(r['baseline_makespan']) / int(r['makespan']), rel_tol=1e-12)
    aggregate = json.loads(read('aggregate.json'))
    assert aggregate == completion['summary']
    for a in aggregate:
        group = [r for r in rows if int(r['cores']) == a['cores']]
        assert len(group) == a['cases'] == 100
        assert sum(int(r['makespan']) for r in group) == a['total_cycles']
        assert sum(int(r['added_copy_bytes']) for r in group) == a['total_added_copy_bytes']
        assert math.isclose(sum(float(r['speedup']) for r in group) / 100, a['mean_speedup'], rel_tol=1e-12)
    verified = json.loads(read('verification.json'))
    assert verified['rows'] == verified['official_replays'] == 500
    assert verified['baseline_matches'] == 100
    assert len(verified['new_search_replays']) == 400
    assert all(r['replay_pass'] for r in verified['new_search_replays'])
    old = {r['case']: r for r in json.loads((ROOT / 'recovered_n5_summary.json').read_text())}
    for r in rows:
        if int(r['cores']) == 5:
            assert int(r['makespan']) == old[r['case']]['makespan']
            assert int(r['added_copy_bytes']) == old[r['case']]['added_copy_bytes']
    for name in ('all_case_results.csv', 'aggregate.json', 'verification.json', 'manifest.json'):
        (OUT / name).write_bytes(read(name))
report = dict(status='PASS', archive_sha256=completion['sha256'], plans=500,
              rows=500, cases_per_core=100, manifest_files=len(manifest),
              checks=['archive SHA-256 and CRC', 'all manifest hashes', '500 distinct configurations',
                      'plan hashes', 'recomputed aggregates', 'server replay records', 'existing five-core consistency'],
              scope='Local integrity and consistency checks; official simulation replay was performed on server, not rerun locally.')
(OUT / 'local_verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(report, ensure_ascii=False))
