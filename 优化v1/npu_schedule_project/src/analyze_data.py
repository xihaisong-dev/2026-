#!/usr/bin/env python3
"""Audit all input DAGs and export deterministic, computation-only graph features.

Run from project root: python src/analyze_data.py
Critical-path features omit communication, spill and resource competition. They are
structural descriptors, not substitutes for the official makespan evaluator.
"""
from __future__ import annotations
import argparse
import csv
import heapq
import json
from collections import Counter, defaultdict
from pathlib import Path


def graph_features(path: Path) -> dict:
    data = json.loads(path.read_text(encoding='utf-8'))
    tensors = {t['id']: t for t in data['tensors']}
    ops = {o['id']: o for o in data['ops']}
    compute = {i: o for i, o in ops.items() if o['op'] not in ('COPY_IN', 'COPY_OUT')}
    producers, consumers, inputs, outputs = (defaultdict(list) for _ in range(4))
    invalid_edges = 0
    all_ids = set(tensors) | set(ops)
    for e in data['edges']:
        a, b = e['source'], e['target']
        if a in tensors and b in ops:
            consumers[a].append(b); inputs[b].append(a)
        elif a in ops and b in tensors:
            producers[b].append(a); outputs[a].append(b)
        else:
            invalid_edges += 1
    pred, succ = ({i: set() for i in compute} for _ in range(2))
    for tid in tensors:
        for a in producers[tid]:
            if a not in compute: continue
            for b in consumers[tid]:
                if b in compute: succ[a].add(b); pred[b].add(a)
    indegree = {i: len(pred[i]) for i in compute}
    queue = [i for i in compute if not indegree[i]]
    heapq.heapify(queue)
    topo, depth, cp = [], {}, {}
    while queue:
        i = heapq.heappop(queue); topo.append(i)
        depth[i] = max((depth[j] + 1 for j in pred[i]), default=0)
        cp[i] = compute[i]['cycles'] + max((cp[j] for j in pred[i]), default=0)
        for j in succ[i]:
            indegree[j] -= 1
            if not indegree[j]: heapq.heappush(queue, j)
    seen = set(); component_sizes = []
    for start in compute:
        if start in seen: continue
        stack = [start]; seen.add(start); count = 0
        while stack:
            i = stack.pop(); count += 1
            for j in succ[i] | pred[i]:
                if j not in seen: seen.add(j); stack.append(j)
        component_sizes.append(count)
    original_move = 0
    for i, o in ops.items():
        if o['op'] == 'COPY_IN':
            original_move += sum(tensors[t]['size'] for t in outputs[i])
        elif o['op'] == 'COPY_OUT':
            original_move += sum(tensors[t]['size'] for t in inputs[i])
    source_tensor_ids = [t for t in tensors if any(i in compute for i in consumers[t]) and not any(i in compute for i in producers[t])]
    work = sum(o['cycles'] for o in compute.values()); critical = max(cp.values(), default=0)
    counts = Counter(o['pipe'] for o in compute.values())
    work_by_pipe = Counter()
    for o in compute.values(): work_by_pipe[o['pipe']] += o['cycles']
    shared = [t for t in source_tensor_ids if sum(i in compute for i in consumers[t]) > 1]
    return dict(case=path.stem, n_tensors=len(tensors), n_ops=len(ops), n_compute_ops=len(compute),
                n_edges=len(data['edges']), n_compute_edges=sum(map(len, succ.values())),
                n_components=len(component_sizes), largest_component_ops=max(component_sizes, default=0),
                dag_depth=max(depth.values(), default=-1) + 1, max_level_width=max(Counter(depth.values()).values(), default=0),
                compute_cycles=work, cube_cycles=work_by_pipe['PIPE_M'], vector_cycles=work_by_pipe['PIPE_V'],
                cube_ops=counts['PIPE_M'], vector_ops=counts['PIPE_V'],
                compute_critical_path_cycles=critical, work_over_critical_path=work/critical if critical else 0,
                original_ddr_bytes=original_move, source_input_bytes=sum(tensors[t]['size'] for t in source_tensor_ids),
                shared_source_tensor_count=len(shared), shared_source_tensor_bytes=sum(tensors[t]['size'] for t in shared),
                max_compute_fanout=max((len(s) for s in succ.values()), default=0),
                tensor_l1_bytes=sum(t['size'] for t in tensors.values() if t['pos']=='L1'),
                tensor_ub_bytes=sum(t['size'] for t in tensors.values() if t['pos']=='UB'),
                unique_ids=len(all_ids)==len(data['tensors'])+len(data['ops']),
                valid_bipartite_edges=invalid_edges==0, compute_dag_valid=len(topo)==len(compute))


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=root/'data')
    parser.add_argument('--output-dir', type=Path, default=root/'results')
    args = parser.parse_args(); args.output_dir.mkdir(parents=True, exist_ok=True)
    paths = sorted(args.data_dir.glob('case_*.json'))
    if not paths: raise SystemExit(f'No case JSON files in {args.data_dir}')
    rows = [graph_features(p) for p in paths]
    target = args.output_dir/'dataset_features.csv'
    with target.open('w', newline='', encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    import numpy as np
    fields = [k for k,v in rows[0].items() if isinstance(v,(int,float)) and not isinstance(v,bool)]
    summary = {'n_cases':len(rows),'all_unique_ids':all(r['unique_ids'] for r in rows),
               'all_valid_bipartite_edges':all(r['valid_bipartite_edges'] for r in rows),
               'all_compute_dags_valid':all(r['compute_dag_valid'] for r in rows),
               'definitions':{'work_over_critical_path':'Total compute cycles / computation-only longest-path cycles; ignores pipe, memory and communication.',
                              'original_ddr_bytes':'Sum of original COPY_IN outputs and COPY_OUT inputs, identical to the official traffic convention.',
                              'n_components':'Weakly connected components of the compute-operation DAG; shared external inputs do not create dependency edges.'},
               'statistics':{k:{'min':float(min(r[k] for r in rows)), 'median':float(np.median([r[k] for r in rows])),
                               'mean':float(np.mean([r[k] for r in rows])), 'max':float(max(r[k] for r in rows))} for k in fields}}
    (args.output_dir/'dataset_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'{len(rows)} cases audited -> {target}')
    print(json.dumps({k:summary['statistics'][k] for k in ('n_compute_ops','n_components','compute_critical_path_cycles','original_ddr_bytes')},ensure_ascii=False,indent=2))

if __name__=='__main__': main()
