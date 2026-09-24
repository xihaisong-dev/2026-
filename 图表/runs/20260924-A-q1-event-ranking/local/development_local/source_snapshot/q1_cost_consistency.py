"""Check exact base-cost cache equivalence on all 500 frozen partitions."""
import argparse
import json
from pathlib import Path
from q1_io import PROCESSED, official, verify, write_json, sha


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    verify(); mod = official()
    from evaluation_validation import read_evaluation_config
    from q1_solver import Graph
    from q1_fast_costs import costs
    settings = read_evaluation_config(str(PROCESSED / 'data/config.txt'))
    waits = mod.read_scene_a_config(str(PROCESSED / 'data/config.txt'))
    args.output.mkdir(parents=True, exist_ok=False)
    checked = []
    for i in range(1, 101):
        case = f'case_{i:03d}'
        raw = json.loads((PROCESSED / 'data' / (case + '.json')).read_text(encoding='utf-8-sig'))
        g = Graph(raw, settings, waits)
        for n in range(1, 6):
            if n == 1:
                mapping = {u: 0 for u in g.ops}
            else:
                plan = json.loads((args.run / case / f'{n}cores_shared_region/plan.json').read_text(encoding='utf-8'))
                mapping = {int(u): s for u, s in plan['node_to_subgraph'].items()}
            expected = g.costs(mapping)
            if costs(g, mapping) != expected or costs(g, mapping) != expected:
                raise RuntimeError('Cost cache mismatch: ' + str((case, n)))
            checked.append({'case': case, 'cores': n, 'cold_and_warm_equal': True})
        write_json(args.output / 'checks.json', {'rows': checked,
            'source_sha256': sha((Path(__file__).parent / 'q1_fast_costs.py').read_bytes())})
        if i % 10 == 0:
            print(i, 'cases checked', flush=True)


if __name__ == '__main__':
    main()
