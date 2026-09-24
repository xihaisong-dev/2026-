"""Reuse only exact plans whose original-official validation is already recorded."""
import gzip, json
from functools import lru_cache
from pathlib import Path
from q1_io import PROCESSED, sha


@lru_cache(maxsize=16)
def summary(path):
    root=Path(path);p=root/'summary.json'
    return json.loads(p.read_text(encoding='utf8')),sha(p.read_bytes())


def reuse_verified(roots, case, cores, plan_path, result):
    normalized=json.loads(json.dumps(result));plan_hash=sha(plan_path.read_bytes())
    for root_name in roots:
        root=Path(root_name);s,summary_hash=summary(str(root))
        if not s.get('completed') or s.get('failures'):continue
        if s['config_sha256']!=sha((PROCESSED/'data/config.txt').read_bytes()):continue
        if s['input_sha256'].get(case+'.json')!=sha((PROCESSED/'data'/f'{case}.json').read_bytes()):continue
        for row in s['runs']:
            if row['case']!=case or row['cores']!=cores or not row.get('verification_passed'):continue
            if row.get('verification_calls')!=1:continue  # No chains of reuse.
            folder=root/f"{case}_{cores}cores_seed{row['seed']}_{row['config']}"
            if row['artifacts']['plan.json']!=plan_hash:continue
            for f in ['plan.json','evaluation.json.gz','verification.json']:
                if sha((folder/f).read_bytes())!=row['artifacts'][f]:raise ValueError('Prior verification artifact corrupted')
            checks=json.loads((folder/'verification.json').read_text(encoding='utf8'))
            if set(checks)!={'makespan','data_movement_bytes','per_core_timeline','memory_peak_by_core','step3_by_task'} or not all(checks.values()):continue
            prior=json.loads(gzip.decompress((folder/'evaluation.json.gz').read_bytes()))
            if normalized!=prior:continue
            # Exact frozen official code/input archive is checked by the caller.
            return checks,dict(source=str(folder),summary_sha256=summary_hash,
                               artifacts={f:row['artifacts'][f] for f in ['plan.json','evaluation.json.gz','verification.json']},
                               policy='byte-identical plan, full normalized result equal, original replay only')
    return None
