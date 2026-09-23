"""最大测试图的构造与合法性检查；不执行完整时间仿真。"""
from pathlib import Path
import json
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from q1_io import ROOT, PROCESSED, official, verify, sha, write_json
from q1_solver import Graph, greedy_partition, multilevel, validate


def main():
    if len(sys.argv) != 2:
        raise SystemExit('Usage: python 程序/tests/check_scale.py <new-output-directory>')
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=False)
    verify()
    official()
    from evaluation_validation import read_evaluation_config
    from multicore_cut_evaluate_problem_1 import read_scene_a_config
    config = str(PROCESSED / 'data/config.txt')
    path = PROCESSED / 'data/case_014.json'
    started = time.perf_counter()
    g = Graph(json.loads(path.read_text(encoding='utf-8-sig')),
              read_evaluation_config(config), read_scene_a_config(config))
    mapping = greedy_partition(g, 4)
    results = []
    for method in ('greedy', 'multilevel'):
        if method == 'multilevel':
            mapping = multilevel(g, mapping, 4)
        plan, _ = g.schedule(mapping, 4)
        validate(g, plan)
        write_json(out / (method + '_plan.json'), plan)
        results.append({'method': method, 'tasks': len(set(mapping.values())),
                        'elapsed_from_start': time.perf_counter() - started,
                        'official_plan_validation': 'PASS',
                        'plan_sha256': sha((out / (method + '_plan.json')).read_bytes())})
        print(method, results[-1], flush=True)
    write_json(out / 'summary.json', {'case': path.name, 'eligible_ops': len(g.ops),
        'input_sha256': sha(path.read_bytes()), 'solver_sha256': sha((ROOT / '程序/q1_solver.py').read_bytes()),
        'full_simulation': 'NOT_RUN', 'results': results})


if __name__ == '__main__':
    main()
