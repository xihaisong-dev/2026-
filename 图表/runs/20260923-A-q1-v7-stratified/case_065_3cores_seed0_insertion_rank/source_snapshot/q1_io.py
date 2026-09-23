"""原始附件的无损导入、校验与官方评估器加载（仅标准库）。"""
from pathlib import Path
import hashlib
import importlib
import json
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ZIP = ROOT / '用户数据/通用神经网络处理器下的多核调度问题  附件.zip'
PROCESSED = ROOT / '数据/processed/q1'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    # Repository enforces LF; binary write keeps recorded hashes identical after Git checkout.
    Path(path).write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


def official(root=PROCESSED):
    code = str((root / 'code').resolve())
    if code not in sys.path:
        sys.path.insert(0, code)
    return importlib.import_module('multicore_cut_evaluate_problem_1')


def verify(root=PROCESSED):
    manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
    for name, expected in manifest['files'].items():
        if sha((root / name).read_bytes()) != expected:
            raise ValueError('输入或评估器哈希不一致: ' + name)
    return manifest


def prepare(source=DEFAULT_ZIP, root=PROCESSED):
    """不清洗或修补原图；验证官方图约束后固化字节哈希。"""
    source = Path(source)
    source_hash = sha(source.read_bytes())
    if (root / 'manifest.json').exists():
        result = verify(root)
        if result['source_sha256'] != source_hash:
            raise ValueError('已存在不同来源的数据；请使用新的导入目录')
        return result
    if root.exists() and any(root.iterdir()):
        raise ValueError('导入目录非空且缺少完成清单，请检查上次失败的导入')
    root.mkdir(parents=True, exist_ok=True)
    files = {}
    with zipfile.ZipFile(source) as archive:
        for name in archive.namelist():
            if not ((name.startswith('code/') and name.endswith('.py')) or
                    (name.startswith('data/') and name.endswith(('.json', '.txt')))):
                continue
            dest = (root / name).resolve()
            if not dest.is_relative_to(root.resolve()):
                raise ValueError('不安全的 ZIP 路径')
            payload = archive.read(name)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(payload)
            files[name] = sha(payload)
    official(root)
    from evaluation_validation import validate_graph
    audit = []
    for path in sorted((root / 'data').glob('case_*.json')):
        graph = json.loads(path.read_text(encoding='utf-8-sig'))
        validate_graph(graph)
        audit.append({'case': path.name, 'ops': len(graph['ops']),
                      'eligible_ops': sum(o['op'] not in {'COPY_IN', 'COPY_OUT'} for o in graph['ops']),
                      'tensors': len(graph['tensors']), 'edges': len(graph['edges'])})
    if not audit:
        raise ValueError('附件未包含测试图')
    result = {'status': 'prototype_input_audited', 'source_sha256': source_hash,
              'transformation': 'byte-identical extraction; official validate_graph on all cases',
              'files': files, 'cases': audit}
    write_json(root / 'manifest.json', result)
    return result
