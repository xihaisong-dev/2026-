"""Transparent post-run correction of task-count display metadata only.

Call only after all 1,500 official results are complete. Original official JSON,
plans, makespans, traffic, cache metrics, timing and selection are not changed.
The computed-source manifests and pre-correction wrapper metadata are archived.
"""
from __future__ import annotations
import argparse
import datetime
import hashlib
import importlib
import json
import shutil
import time
import zipfile
from pathlib import Path
import evaluate
from evaluate import ROOT, read_json, write_json, sha256_file
from solver import generate_candidates
from singlecore_evaluate import build_singlecore_plan

HELPER='''def _executed_task_count(result, plan=None):
    """Count actual nonempty execution tasks; idle core contexts are excluded."""
    if plan is not None:
        if result.get('scene') == 'A':
            return len(set(plan['node_to_subgraph'].values()))
        return sum(bool(order) for order in plan['core_schedules'])
    if result.get('scene') == 'A':
        return len(result.get('step3_by_task', {}))
    return sum(bool(core.get('ops')) for core in result.get('per_core_timeline', []))


'''


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--results',type=Path,default=ROOT/'results')
    args=ap.parse_args();out=args.results
    marker=out/'metadata_corrections.json'
    if marker.exists():print('Metadata correction already completed; no changes.');return
    records=sorted((out/'records').glob('*.json'))
    rows=[r for f in records for r in read_json(f)]
    expected={(f.stem,p,n) for f in (ROOT/'data').glob('case_*.json') for p in (1,2,3) for n in (1,2,3,4,5)}
    assert len(rows)==1500 and {(r['case'],r['problem'],r['cores']) for r in rows}==expected,'All 1,500 configurations must exist first'
    current_text=(ROOT/'src/evaluate.py').read_text(encoding='utf-8')
    if "task_count=result.get('task_count', 1)," not in current_text and "official_task_count=result.get('task_count')" in current_text and all('task_count' not in r for r in rows):
        print('Current source and all records already use unambiguous task-count metadata; no migration needed.');return
    original=read_json(out/'run_manifest.json')
    for name,digest in original['source_sha256'].items():assert sha256_file(ROOT/'src'/name)==digest,'Source changed before metadata correction: '+name
    certified=read_json(out/'certified_engine_manifest.json') if (out/'certified_engine_manifest.json').exists() else None
    if certified:
        for name,digest in certified['source_sha256'].items():assert sha256_file(ROOT/'src'/name)==digest,'Certified source changed: '+name
    start=time.perf_counter();archive=out/'provenance/metadata_revision';archive.mkdir(parents=True,exist_ok=True)
    source_names=set(original['source_sha256']) | (set(certified['source_sha256']) if certified else set())
    for name in source_names:shutil.copy2(ROOT/'src'/name,archive/name)
    for name in ('run_manifest.json','certified_engine_manifest.json'):
        if (out/name).exists():shutil.copy2(out/name,archive/name)
    official_paths=sorted((out/'official_results').glob('*.json.gz'))+sorted((out/'baselines').glob('*.json.gz'))
    official_hashes={str(p.relative_to(out)):sha256_file(p) for p in official_paths}
    wrappers=records+sorted((out/'candidates').glob('*.json'))+sorted((out/'candidate_checkpoints').glob('*.json'))+sorted((out/'baselines').glob('*.meta.json'))
    with zipfile.ZipFile(archive/'wrapper_metadata_before.zip','w',compression=zipfile.ZIP_DEFLATED) as z:
        for path in wrappers:z.write(path,path.relative_to(out))
    source=ROOT/'src/evaluate.py';before_source=sha256_file(source);text=source.read_text()
    old="task_count=result.get('task_count', 1),"
    assert text.count(old)==1,'Expected unique original metadata expression'
    text=text.replace('def flatten_result(',HELPER+'def flatten_result(',1).replace(old,"official_task_count=result.get('task_count'),\n               executed_task_count_derived=_executed_task_count(result, plan),")
    temporary_source=source.with_suffix('.metadata.tmp');temporary_source.write_text(text,encoding='utf-8');temporary_source.replace(source);importlib.reload(evaluate)
    changes=[];graph_cache={};candidate_cache={}
    def remember(path,old_value,new_value):
        def unchanged_payload(value):
            if isinstance(value,list):return [unchanged_payload(item) for item in value]
            return {key:item for key,item in value.items() if key not in ('task_count','official_task_count','executed_task_count_derived')}
        assert unchanged_payload(old_value)==unchanged_payload(new_value),'Non-metadata value changed: '+str(path)
        before=sha256_file(path)
        if old_value!=new_value:
            write_json(path,new_value);changes.append(dict(file=str(path.relative_to(out)),before_sha256=before,after_sha256=sha256_file(path)))
    for path in records:
        old_rows=read_json(path);new_rows=[]
        for old_row in old_rows:
            row=dict(old_row);plan=read_json(out/row['plan_path']);actual=read_json(out/row['official_result_path'])
            row.pop('task_count',None);row['official_task_count']=actual.get('task_count');row['executed_task_count_derived']=evaluate._executed_task_count(actual,plan)
            new_rows.append(row)
        remember(path,old_rows,new_rows)
    def plan_map(case,n,problem):
        key=(case,n,problem)
        if key in candidate_cache:return candidate_cache[key]
        if case not in graph_cache:graph_cache[case]=read_json(ROOT/'data'/(case+'.json'))
        graph=graph_cache[case];single=build_singlecore_plan(graph);single['core_schedules'] += [[] for _ in range(n-1)]
        value=dict(generate_candidates(graph,n,problem,budget=original['budget'])) if n>1 else {}
        value.update(whole_graph=single,official_singlecore=single)
        candidate_cache[key]=value;return value
    for folder in ('candidates','candidate_checkpoints'):
        for path in sorted((out/folder).glob('*.json')):
            case,rest=path.stem.rsplit('_p',1);problem_text,n_text=rest.split('_n');problem,n=int(problem_text),int(n_text)
            old_rows=read_json(path);new_rows=[]
            for old_row in old_rows:
                row=dict(old_row);row.pop('task_count',None)
                from_b=(problem==2 or row.get('score_source')=='certified_official_B')
                row['official_task_count']=n if from_b else None
                if problem==1 and row.get('subgraph_count') is not None:
                    count=row['subgraph_count']
                else:
                    plan=plan_map(case,n,problem).get(row['method'])
                    if plan is None:raise AssertionError('Cannot regenerate candidate plan: '+path.name+' '+row['method'])
                    count=len(set(plan['node_to_subgraph'].values())) if problem==1 else sum(bool(x) for x in plan['core_schedules'])
                row['executed_task_count_derived']=count;new_rows.append(row)
            remember(path,old_rows,new_rows)
    for path in sorted((out/'baselines').glob('*.meta.json')):
        old_row=read_json(path);row=dict(old_row);row.pop('task_count',None);row['official_task_count']=None;row['executed_task_count_derived']=1
        remember(path,old_row,row)
    for rel,digest in official_hashes.items():assert sha256_file(out/rel)==digest,'An original official result was changed'
    revised=dict(original);revised['source_sha256']={name:sha256_file(ROOT/'src'/name) for name in original['source_sha256']};write_json(out/'run_manifest.json',revised)
    if certified:
        revised_c=dict(certified);revised_c['source_sha256']={name:sha256_file(ROOT/'src'/name) for name in certified['source_sha256']};revised_c['frozen_run_manifest_sha256']=sha256_file(out/'run_manifest.json');write_json(out/'certified_engine_manifest.json',revised_c)
    revision=dict(kind='metadata_only',at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),source_file='src/evaluate.py',source_before_sha256=before_source,source_after_sha256=sha256_file(source),reason='The official A evaluator has no task_count key; the old wrapper defaulted it to one. B/C count idle core contexts as task slots. Replace that ambiguous wrapper field with official_task_count and executed_task_count_derived.',unchanged='No official source, plan, official full result, score, selected method, makespan, traffic, cache or timing value was modified.',computed_source_archive='provenance/metadata_revision',current_manifests='Current manifests identify the metadata-corrected replay code. The exact manifests used to compute the delivered official results remain archived in provenance/metadata_revision.')
    write_json(out/'source_revisions.json',[revision])
    write_json(marker,dict(status='PASS',corrected_wrapper_files=len(changes),changed_fields=['task_count (removed)','official_task_count','executed_task_count_derived'],official_result_hashes_unchanged=official_hashes,changes=changes,archive_sha256=sha256_file(archive/'wrapper_metadata_before.zip'),elapsed_seconds=time.perf_counter()-start))
    from run_experiments import aggregate
    aggregate(out)
    print('PASS: metadata correction;',len(changes),'wrapper files;',len(official_hashes),'official files byte-identical')

if __name__=='__main__':main()
