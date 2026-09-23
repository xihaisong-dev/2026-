"""Exact indexed/counter backend derived from the pinned official evaluator.

The official files remain untouched. Only the repeated Task completion scan is
replaced: remaining starts at len(seq), falls once per retired op, and is zero
iff the original all(done) predicate is true. Event ordering, DDR arithmetic,
Step3 scheduling and output construction are unchanged. A reverse tensor index
replaces the repeated all-tensor scan, retaining sorted order and boundary IDs.
Only active Tasks need retirement checks, in their original dictionary order;
len(task_end) counts completed Tasks exactly. Timeline indexing preserves order.
This is a full scoring
evaluation and MUST consume the same search budget as the official backend.
"""
import hashlib
import inspect
from functools import lru_cache
from pathlib import Path

OFFICIAL_SHA256 = '2095f188a6c24ce3899f156bef21d50dcd87cbd9368488046b1e77e2bf91af3f'
BACKEND_ID = 'indexed-counter-v3:' + OFFICIAL_SHA256


@lru_cache(maxsize=1)
def evaluator():
    from q1_io import official
    module = official()
    if hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest() != OFFICIAL_SHA256:
        raise ValueError('Unsupported official evaluator: completion-counter patch refused')
    source = inspect.getsource(module.evaluate_scene_a)
    replacements = [
        ("    task_start, task_end = {}, {}",
         "    remaining_ops = {tid: len(task['seq']) for tid, task in tasks.items()}\n"
         "    task_rank = {tid: i for i, tid in enumerate(tasks)}\n"
         "    task_start, task_end = {}, {}"),
        ("                op_status[item] = 'done'",
         "                remaining_ops[task_id] -= 1\n"
         "                op_status[item] = 'done'"),
        ("            task_items = [key(task_id, op_id) for op_id in tasks[task_id]['seq']]\n"
         "            if all(op_status[item] == 'done' for item in task_items):",
         "            if remaining_ops[task_id] == 0:"),
        ("        for task_id, status in list(task_status.items()):\n"
         "            if status != 'active':\n"
         "                continue",
         "        for task_id in sorted((t for t in core_active_task.values() if t is not None), key=task_rank.__getitem__):"),
        ("        if all(status == 'done' for status in task_status.values()):",
         "        if len(task_end) == len(tasks):"),
        ("        subgraph_entries = []",
         "        ops_by_task = {tid: [] for tid in core_orders.get(core_id, [])}\n"
         "        for entry in op_entries:\n"
         "            ops_by_task[entry['task_id']].append(entry)\n"
         "        subgraph_entries = []"),
        ("            subgraph_ops = [entry for entry in op_entries\n"
         "                            if entry['task_id'] == task_id]",
         "            subgraph_ops = ops_by_task[task_id]"),
    ]
    for before, after in replacements:
        if source.count(before) != 1:
            raise ValueError('Official function structure changed; patch refused')
        source = source.replace(before, after)
    namespace = dict(vars(module))
    task_source = inspect.getsource(module._build_scene_a_tasks)
    task_replacements = [
        ("    core_by_task = plan_view['core_by_subgraph']",
         "    touched_by_task = {tid: set() for tid in plan_view['subgraph_ids']}\n"
         "    for tensor_id in tensor_by_id:\n"
         "        for op_id in producers.get(tensor_id, set()) | consumers.get(tensor_id, set()):\n"
         "            if op_id in mapping:\n"
         "                touched_by_task[mapping[op_id]].add(tensor_id)\n"
         "    core_by_task = plan_view['core_by_subgraph']"),
        ("        touched_tensors = sorted(\n"
         "            tensor_id for tensor_id in tensor_by_id\n"
         "            if producers.get(tensor_id, set()) & task_op_ids\n"
         "            or consumers.get(tensor_id, set()) & task_op_ids)",
         "        touched_tensors = sorted(touched_by_task[task_id])"),
    ]
    for before, after in task_replacements:
        if task_source.count(before) != 1:
            raise ValueError('Official Task construction changed; patch refused')
        task_source = task_source.replace(before, after)
    exec(compile(task_source, '<q1-indexed-task-construction-v2>', 'exec'), namespace)
    exec(compile(source, '<q1-indexed-counter-v3>', 'exec'), namespace)
    return namespace['evaluate_scene_a']


def evaluate_scene_a(*args, **kwargs):
    return evaluator()(*args, **kwargs)
