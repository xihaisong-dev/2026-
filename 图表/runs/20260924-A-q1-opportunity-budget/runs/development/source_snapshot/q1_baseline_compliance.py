"""Read-only scene-A evidence audit; does not change solver or official code."""
import argparse
from collections import Counter, defaultdict
import gzip
import json
from pathlib import Path
from statistics import mean
import time
from zipfile import ZipFile

from q1_io import ROOT, PROCESSED, DEFAULT_ZIP, official, sha, verify, write_json


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def result(path):
    return json.loads(gzip.decompress(path.read_bytes()))


def check_timeline(raw, plan, evaluation, settings, waits):
    from stub_multicore_cut_and_schedule import derive_multicore_plan
    from evaluation_validation import validate_task_order
    from multicore_cut_evaluate_problem_1 import PIPE_SLOTS
    view = derive_multicore_plan(raw, plan)
    validate_task_order(view)
    mapping = {int(u): s for u, s in plan['node_to_subgraph'].items()}
    assert all(isinstance(u, str) and u == str(int(u)) for u in plan['node_to_subgraph'])
    assert evaluation['scene'] == 'A'
    assert evaluation['num_cores'] == len(plan['core_schedules'])
    assert evaluation['bandwidth_bytes_per_cycle'] == settings['bandwidth'] == 60
    assert evaluation['capacity_bytes'] == settings['capacity']
    assert evaluation['task_cross_core_wait_cycles'] == waits['task_cross_core_wait_cycles'] == 1000
    assert evaluation['task_same_core_wait_cycles'] == waits['task_same_core_wait_cycles'] == 100
    owner, tasks, compute, all_ends = {}, {}, {}, []
    assert len(evaluation['per_core_timeline']) == len(plan['core_schedules'])
    for core, timeline in enumerate(evaluation['per_core_timeline']):
        assert timeline['core_id'] == core
        assert [t['task_id'] for t in timeline['tasks']] == plan['core_schedules'][core]
        for task in timeline['tasks']:
            task_id = task['task_id']
            assert task_id == task['subgraph_id'] and task_id not in tasks
            assert task['start'] >= 0 and task['end'] - task['start'] == task['duration']
            owner[task_id], tasks[task_id] = core, task
        for left, right in zip(timeline['tasks'], timeline['tasks'][1:]):
            assert right['start'] >= left['end'] + 100
        events = defaultdict(lambda: defaultdict(int))
        for op in timeline['ops']:
            task = tasks[op['task_id']]
            assert task['start'] <= op['start'] <= op['end'] <= task['end']
            assert op['end'] - op['start'] == op['duration']
            all_ends.append(op['end'])
            if op['end'] > op['start']:
                events[op['pipe']][op['start']] += 1
                events[op['pipe']][op['end']] -= 1
            if op['op_id'] in mapping:
                assert op['op_id'] not in compute
                assert mapping[op['op_id']] == op['task_id']
                compute[op['op_id']] = op
        for positions in events.values():
            active = 0
            for t in sorted(positions):
                active += positions[t]
                assert 0 <= active <= PIPE_SLOTS
            assert active == 0
        for memory, peak in evaluation['memory_peak_by_core'][str(core)].items():
            assert 0 <= peak <= settings['capacity'][memory]
    assert set(compute) == set(mapping)
    assert set(tasks) == set(mapping.values())
    assert set(map(int, evaluation['step3_by_task'])) == set(tasks)
    assert evaluation['makespan'] == max(all_ends, default=0)
    assert {(d['source'], d['target']) for d in evaluation['task_dependencies']} == set(view['dependency_pairs'])
    for src, dst in view['dependency_pairs']:
        assert tasks[dst]['start'] >= tasks[src]['end'] + (1000 if owner[src] != owner[dst] else 0)
    op_by_id = {o['id']: o for o in raw['ops']}
    tensors = {t['id']: t for t in raw['tensors']}
    producers, consumers = defaultdict(set), defaultdict(set)
    original = 0
    for edge in raw['edges']:
        u, v = edge['source'], edge['target']
        if u in op_by_id:
            producers[v].add(u)
            if op_by_id[u]['op'] == 'COPY_IN':
                original += tensors[v]['size']
        else:
            consumers[u].add(v)
            if op_by_id[v]['op'] == 'COPY_OUT':
                original += tensors[u]['size']
    boundary = cross = 0
    for tid, tensor in tensors.items():
        ps, cs = producers[tid] & mapping.keys(), consumers[tid] & mapping.keys()
        p_tasks, c_tasks = {mapping[u] for u in ps}, {mapping[u] for u in cs}
        boundary += tensor['size'] * len(c_tasks - p_tasks)
        final_output = any(op_by_id[u]['op'] == 'COPY_OUT' for u in consumers[tid])
        for p_task in p_tasks:
            if final_output or not cs or c_tasks - {p_task}:
                boundary += tensor['size']
            cross += tensor['size'] * len(c_tasks - {p_task})
        for u in ps:
            for v in cs:
                assert compute[v]['start'] >= compute[u]['end']
    for u, op in compute.items():
        assert op['op'] == op_by_id[u]['op'] and op['pipe'] == op_by_id[u]['pipe']
        assert op['duration'] >= op_by_id[u]['cycles']
    traffic = evaluation['data_movement_bytes']
    assert traffic['original_graph_copy_bytes'] == original
    assert traffic['partition_added_copy_bytes'] == boundary - original
    assert traffic['scheduled_copy_bytes'] == boundary + traffic['spill_added_copy_bytes']
    assert traffic['added_copy_bytes'] == traffic['scheduled_copy_bytes'] - original
    assert evaluation['cross_task_traffic'] == cross
    return len(tasks)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--replay-samples', action='store_true')
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    manifest = verify()
    assert sha(DEFAULT_ZIP.read_bytes()) == manifest['source_sha256']
    with ZipFile(DEFAULT_ZIP) as archive:
        for name, digest in manifest['files'].items():
            assert sha(archive.read(name)) == digest
    evaluator = official()
    from evaluation_validation import read_evaluation_config
    from singlecore_evaluate import build_singlecore_plan
    settings = read_evaluation_config(str(PROCESSED/'data/config.txt'))
    waits = evaluator.read_scene_a_config(str(PROCESSED/'data/config.txt'))
    report = read(args.run/'summary.json')
    assert report['completed'] and len(report['cases']) == 100
    assert {c['case'] for c in report['cases']} == {f'case_{i:03d}' for i in range(1,101)}
    for name, digest in report['code_sha256'].items():
        assert sha((args.run/'source_snapshot'/name).read_bytes()) == digest
    expected_features = ['comm_rank','critical','insertion','local_cost','partition_guard','region','shared_input']
    rows, singles, replayed = [], [], []
    samples = {('case_001',2), ('case_048',5), ('case_067',3), ('case_084',4)}
    for item in sorted(report['cases'], key=lambda r:r['case']):
        case = item['case']
        raw = read(PROCESSED/'data'/f'{case}.json')
        single = result(args.run/case/'single/evaluation.json.gz')
        check_timeline(raw, build_singlecore_plan(raw), single, settings, waits)
        assert single['makespan'] == item['single']['makespan']
        singles.append({'case':case, 'makespan':single['makespan'],
                        'original_compute_seconds':item['single'].get('reference_compute_seconds')})
        for cores in [2,3,4,5]:
            folder = args.run/case/f'{cores}cores_shared_region'
            row, stats, plan = (read(folder/name) for name in ['row.json','search.json','plan.json'])
            for name, digest in row['artifacts'].items():
                assert sha((folder/name).read_bytes()) == digest
            assert len(plan['core_schedules']) == cores
            evaluation = result(folder/'evaluation.json.gz')
            task_count = check_timeline(raw, plan, evaluation, settings, waits)
            assert stats['features'] == expected_features and stats['seed'] == 0
            assert stats['evaluation_budget'] == 12 and len(stats['evaluations']) <= 12
            assert stats['official_calls'] + stats['cache_hits'] == len(stats['evaluations'])
            assert stats['singlecore_makespan'] == single['makespan']
            score = (evaluation['makespan'], evaluation['data_movement_bytes']['added_copy_bytes'])
            assert score == min((v['makespan'],v['added_copy_bytes']) for v in stats['evaluations'])
            assert row['makespan'] == score[0] and row['added_copy_bytes'] == score[1]
            assert row['speedup'] == single['makespan']/score[0]
            rows.append({'case':case,'cores':cores,'makespan':score[0],'added_copy_bytes':score[1],
                         'speedup':row['speedup'],'seconds':row['seconds'],'tasks':task_count})
            if args.replay_samples and (case,cores) in samples:
                start = time.perf_counter()
                again = evaluator.evaluate_scene_a(raw, plan, settings['bandwidth'],settings['capacity'],1000,100)
                # Normalize JSON integer/string dictionary keys, preserving every result field.
                assert json.loads(json.dumps(again)) == evaluation, (case,cores)
                replayed.append({'case':case,'cores':cores,'full_result_equal':True,'seconds':time.perf_counter()-start})
                write_json(args.output/'replay_progress.json',replayed)
        print('AUDIT',case,flush=True)
    output = {'scope':'v18 shared_region seed 0, 100 cases x 2-5 cores',
              'status':'technical_checks_passed_submission_and_runtime_require_review',
              'source_summary_sha256':sha((args.run/'summary.json').read_bytes()),
              'auditor_sha256':sha(Path(__file__).read_bytes()),'source_zip_sha256':manifest['source_sha256'],
              'verified_files_against_original_zip':len(manifest['files']),
              'verified_single_results':len(singles),'verified_multicore_results':len(rows),
              'mean_speedup':{'1':1.0,**{str(k):mean(r['speedup'] for r in rows if r['cores']==k) for k in [2,3,4,5]}},
              'baseline_runs_over_600_seconds':[r for r in rows if r['seconds']>600],
              'single_baselines_over_600_seconds':[r for r in singles if r['original_compute_seconds'] and r['original_compute_seconds']>600],
              'replayed_samples':replayed,'results':rows,
              'limits':['full fresh official replay limited to listed samples',
                        'recorded timings mix hosts, warm caches and resumed attempts',
                        'official saved memory peaks checked; not an independent memory allocator proof',
                        'no formal workflow gate approval implied']}
    write_json(args.output/'audit.json',output)
    print('PASS 100 single + 400 baseline; fresh replay samples',len(replayed))


if __name__ == '__main__':
    main()
