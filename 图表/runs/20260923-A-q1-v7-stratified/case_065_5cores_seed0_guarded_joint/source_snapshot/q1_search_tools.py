"""Fixed-plan timing diagnostics, bounded joint neighborhoods and verified result reuse."""
from collections import Counter
import copy
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import tempfile

from q1_solver import topological, validate


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


class EvaluationCache:
    def __init__(self, folder, raw, settings, waits):
        from q1_io import PROCESSED
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        files = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in sorted((PROCESSED/'code').glob('*.py'))}
        if not files:
            raise ValueError('Missing evaluator sources')
        self.context = {'schema': 1, 'raw': raw, 'settings': settings, 'waits': waits,
                        'evaluator': files, 'python': platform.python_version()}
        self.namespace = hashlib.sha256(canonical(self.context)).hexdigest()

    def run(self, plan, compute):
        key = hashlib.sha256(canonical([self.namespace, plan])).hexdigest()
        path = self.folder / (key+'.json.gz')
        if path.exists():
            record = json.loads(gzip.decompress(path.read_bytes()))
            if record['key'] != key or hashlib.sha256(canonical(record['result'])).hexdigest() != record['sha256']:
                raise ValueError('Evaluation cache integrity failure')
            return record['result'], True
        result = json.loads(json.dumps(compute(), ensure_ascii=False))
        record = {'key': key, 'result': result, 'sha256': hashlib.sha256(canonical(result)).hexdigest()}
        payload = gzip.compress(canonical(record), mtime=0)
        fd, name = tempfile.mkstemp(dir=self.folder, suffix='.tmp')
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(payload)
            os.replace(name, path)
        finally:
            if os.path.exists(name):
                os.unlink(name)
        return result, False


def replay(g, plan, durations, waits=True):
    mapping = {int(u): s for u, s in plan['node_to_subgraph'].items()}
    groups, pred, succ, _ = g.view(mapping)
    owner = {s: c for c, seq in enumerate(plan['core_schedules']) for s in seq}
    previous = {b: a for seq in plan['core_schedules'] for a, b in zip(seq, seq[1:])}
    edges = {(a, b): (g.cross if owner[a] != owner[b] else 0) if waits else 0
             for a in groups for b in succ[a]}
    for b, a in previous.items():
        pred[b].add(a)
        succ[a].add(b)
        edges[a, b] = max(edges.get((a, b), 0), g.same if waits else 0)
    end = {}
    for s in topological(pred, succ):
        end[s] = max((end[a] + edges[a, s] for a in pred[s]), default=0) + durations[s]
    return max(end.values(), default=0)


def diagnose(g, plan, result, predicted):
    local = {int(s): v['local_makespan'] for s, v in result['step3_by_task'].items()}
    isolated = replay(g, plan, local)
    no_wait = replay(g, plan, local, False)
    return {'predicted_makespan': predicted, 'official_makespan': result['makespan'],
            'local_profile_replay': isolated, 'local_model_residual': isolated-predicted,
            'global_replay_residual': result['makespan']-isolated,
            'fixed_profile_wait_effect': isolated-no_wait,
            'ddr_contention_events': len(result['ddr_contention_log']),
            'max_active_ddr': max((x['active_count'] for x in result['ddr_contention_log']), default=0)}


def ranked_joint(g, plan, result, cores, ddr=False):
    from q1_experimental import task_slacks
    from q1_lookahead import candidates
    mapping = {int(u): s for u, s in plan['node_to_subgraph'].items()}
    groups, pred, succ, order = g.view(mapping)
    positions = {s: i for i, s in enumerate(order)}
    tasks = [t for c in result['per_core_timeline'] for t in c['tasks']]
    slack = task_slacks(g, plan, result)
    local = {int(s): v['local_makespan'] for s, v in result['step3_by_task'].items()}
    congestion = Counter(x['issued']['task_id'] for x in result['ddr_contention_log'] if x['active_count'] > 1)
    tasks.sort(key=lambda t: ((-congestion[t['task_id']], -(t['duration']-local[t['task_id']])) if ddr
                             else (slack[t['task_id']], -t['duration'])) + (t['task_id'],))
    pool, seen = [], set()

    def add(label, trial):
        key = canonical(trial)
        if key in seen or trial == plan:
            return
        seen.add(key)
        try:
            validate(g, trial)
            costs = g.costs({int(u): s for u, s in trial['node_to_subgraph'].items()})[0]
            score = replay(g, trial, costs)
        except ValueError:
            return
        pool.append((score, label, trial))

    if not ddr:
        for label, trial in candidates(g, plan, result, cores):
            add(label, trial)
    for task in tasks[:2]:
        s = task['task_id']
        source = next(c for c, seq in enumerate(plan['core_schedules']) if s in seq)
        for target in range(cores):
            if target == source:
                continue
            trial = copy.deepcopy(plan)
            trial['core_schedules'][source].remove(s)
            trial['core_schedules'][target].append(s)
            trial['core_schedules'][target].sort(key=positions.get)
            add(f'migrate_{s}_{target}', trial)
        if ddr:
            seq = plan['core_schedules'][source]
            i = seq.index(s)
            for j in [i-1, i+1]:
                if 0 <= j < len(seq):
                    trial = copy.deepcopy(plan)
                    trial['core_schedules'][source][i], trial['core_schedules'][source][j] = seq[j], seq[i]
                    add(f'ddr_reorder_{s}_{j}', trial)
        else:
            # Move boundary operations in either direction and jointly remap the graph.
            boundary = [(u, v) for u in sorted(groups[s]) for v in sorted(g.succ[u]) if mapping[v] != s]
            boundary += [(u, v) for v in sorted(groups[s]) for u in sorted(g.pred[v]) if mapping[u] != s]
            for u, v in boundary[:4]:
                for a, b in [(u, v), (v, u)]:
                    trial_map = dict(mapping)
                    trial_map[a] = mapping[b]
                    try:
                        add(f'boundary_{a}_{b}', g.schedule(trial_map, cores)[0])
                    except ValueError:
                        continue
    for _, label, trial in sorted(pool, key=lambda x: (x[0], x[1])):
        yield label, trial


def choose_arm(arms, pulls, rewards, attempt):
    # Reserve one quarter of proposals for a deterministic rotating exploration arm.
    if attempt % 4 == 0:
        return arms[(attempt//4) % len(arms)]
    unseen = next((a for a in arms if pulls[a] == 0), None)
    if unseen:
        return unseen
    return max(arms, key=lambda a: (rewards[a]/pulls[a], -pulls[a], -arms.index(a)))
