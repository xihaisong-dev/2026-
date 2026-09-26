"""Replay fixed plans against saved full official results, without searching."""
import argparse
import concurrent.futures
import csv
import gzip
import hashlib
import json
import platform
import time
from pathlib import Path
from q1_io import ROOT, PROCESSED, official, verify, write_json


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical(value):
    # JSON object keys are strings on disk; preserve every field and list order.
    return json.loads(json.dumps(value, ensure_ascii=False))


def first_difference(a, b, path='$'):
    if type(a) != type(b):
        return path + ': type differs'
    if isinstance(a, dict):
        if a.keys() != b.keys():
            return path + ': keys differ ' + str(a.keys() ^ b.keys())
        for key in a:
            d = first_difference(a[key], b[key], path + '.' + key)
            if d: return d
    elif isinstance(a, list):
        if len(a) != len(b): return path + ': length differs'
        for i, (x, y) in enumerate(zip(a, b)):
            d = first_difference(x, y, path + f'[{i}]')
            if d: return d
    elif a != b:
        return path + ': ' + repr(a)[:100] + ' != ' + repr(b)[:100]
    return None


def worker(job):
    started = time.perf_counter()
    graph = PROCESSED / 'data' / (job['case'] + '.json')
    raw = json.loads(graph.read_text('utf-8-sig'))
    plan = json.loads(Path(job['plan']).read_text('utf-8'))
    reference_bytes = Path(job['reference']).read_bytes()
    expected = json.loads(gzip.decompress(reference_bytes))
    mod = official()
    from evaluation_validation import read_evaluation_config
    from q1_fast_evaluator import evaluate_scene_a
    config = PROCESSED / 'data/config.txt'
    settings = read_evaluation_config(str(config)); waits = mod.read_scene_a_config(str(config))
    t = time.perf_counter()
    actual = evaluate_scene_a(raw, plan, settings['bandwidth'], settings['capacity'],
        waits['task_cross_core_wait_cycles'], waits['task_same_core_wait_cycles'])
    eval_seconds = time.perf_counter() - t
    # These two fields are attached by the official singlecore CLI wrapper.
    if job['cores'] == 1 and 'execution_mode' in expected:
        assert expected['execution_mode'] == 'singlecore' and expected['input_plan'] is None
        actual.update(execution_mode='singlecore', input_plan=None)
    actual = canonical(actual)
    difference = first_difference(expected, actual)
    actual_hash = hashlib.sha256(json.dumps(actual, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    row = dict(case=job['case'], cores=job['cores'], equal=difference is None,
        difference=difference, evaluation_seconds=eval_seconds,
        total_seconds=time.perf_counter()-started, graph_sha256=sha(graph),
        config_sha256=sha(config), plan_sha256=sha(job['plan']),
        reference_sha256=sha(job['reference']), full_result_canonical_sha256=actual_hash,
        makespan=actual['makespan'], added_copy_bytes=actual['data_movement_bytes']['added_copy_bytes'],
        host=platform.node(), python=platform.python_version(),
        reference=job['reference'], plan=job['plan'])
    write_json(Path(job['output']), row)
    return row


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--mode', choices=['pilot', 'full'], required=True)
    p.add_argument('--workers', type=int, default=3)
    a = p.parse_args(); verify()
    a.output.mkdir(parents=True, exist_ok=False)
    jobs = []
    if a.mode == 'pilot':
        for n in (72,76):
            base = ROOT / f'图表/runs/20260926-A-q123-cold-audit/case_{n:03}/5/q1'
            jobs.append(dict(case=f'case_{n:03}', cores=5,
                plan=str(base/f'case_{n:03}_multicore_res.json'), reference=str(base/'evaluation.json.gz')))
    else:
        with (ROOT/'图表/runs/20260924-A-q1-delivery-r02/all_case_results.csv').open(encoding='utf-8-sig') as f:
            for row in csv.DictReader(f):
                k=int(row['cores']);case=row['case']
                ref=ROOT/row['source']/'evaluation.json.gz'
                assert sha(ref)==row['evaluation_sha256'], f'Reference hash differs: {ref}'
                jobs.append(dict(case=case, cores=k,
                    plan=str(ROOT/f'图表/runs/20260924-A-q1-delivery-r02/solutions/{k}cores/{case}_multicore_res.json'),reference=str(ref)))
    for j in jobs:
        j['output']=str(a.output/f"{j['case']}_{j['cores']}cores.json")
        j['frozen_plan_sha256']=sha(j['plan']);j['frozen_reference_sha256']=sha(j['reference'])
    write_json(a.output/'contract.json', dict(mode=a.mode, workers=a.workers, jobs=jobs,
        method='fresh accelerated full evaluation vs saved full official JSON; no field dropped; singlecore CLI metadata restored',
        source_sha256={f:sha(ROOT/'程序'/f) for f in ('q1_equivalent_replay_audit.py','q1_fast_evaluator.py')}))
    rows=[];begin=time.perf_counter()
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers) as ex:
        for row in ex.map(worker,jobs):
            rows.append(row)
            assert row['plan_sha256']==next(j['frozen_plan_sha256'] for j in jobs if j['case']==row['case'] and j['cores']==row['cores'])
            print(json.dumps({k:row[k] for k in ('case','cores','equal','evaluation_seconds','difference')}),flush=True)
    summary=dict(expected=len(jobs),completed=len(rows),equal=sum(r['equal'] for r in rows),
        failures=[r for r in rows if not r['equal']],wall_seconds=time.perf_counter()-begin)
    write_json(a.output/'summary.json',summary)
    if summary['equal'] != len(jobs):raise SystemExit(1)


if __name__ == '__main__':main()
