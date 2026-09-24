"""Build a self-contained Q1 baseline reproduction archive from frozen evidence."""
import argparse
import csv
import json
from pathlib import Path
import shutil
from statistics import mean
from zipfile import ZipFile, ZIP_DEFLATED
from q1_io import ROOT, PROCESSED, DEFAULT_ZIP, sha, verify, write_json, official

GUIDE = '''# 问题一基线复现包

这是 shared_region 基线；100图、固定配置、种子0、每个多核配置12次候选评价机会。
依赖 Python >=3.10 标准库；本轮在 Python 3.14.6 验证。解压后在本目录运行。

1. 校验所有交付文件（清单不包含自身）：`python verify_package.py`
2. 单图复现（完整官方复核会增加运行时间）：
   `python 程序/q1_submit.py 数据/processed/q1/data/case_001.json -n 5 --output trial_001 --verify-final`
3. 全部100图×1～5核：
   `python 程序/q1_reproduce.py --output reproduced --workers 2`
   内存充足时提高 workers；16GB机器建议2个。每个case的单核固定基准只算一次并复用。
4. 原始官方后端：以上命令追加 `--backend official`。此后端可能明显更慢。
5. 单元测试：`python -m unittest discover -s 程序/tests`

输出目录必须不存在，避免覆盖已有结果。单图输出 `<case>_multicore_res.json` 仅含
node_to_subgraph 和 core_schedules；评价时间线、参数与日志独立保存。
导出的 solutions/2cores 至 5cores 含400份正式多核方案，1cores含100份整图基准方案。
results/all_case_results.csv 是500条官方历史结果，不是新后端重算的成绩。
平均加速比为100个 T1/Tk 的算术平均，严禁用总时间比替代。

当前默认 counter 后端把官方事件模拟的 Task 完成扫描换为计数，预建张量/时间线索引，
只检查活跃Task；基础代理成本按成员复用。原官方代码不改动；
完整全局模拟仍计入12次预算，不算免费代理。确切验证范围与耗时见 runtime/。
比赛Makespan、额外搬运量保持原基线数值，不把评估器加速声称为调度提速。
保留 frozen_v18/ 原搜索源码用于历史审计；当前完整源码与数据由 package_manifest.json 固化。
本包是问题一算法/结果支撑材料；不表示三问论文、人工验收或正式工作流已完成。
'''

VERIFY = '''import hashlib, json
from pathlib import Path
root = Path(__file__).resolve().parent
m = json.loads((root/'package_manifest.json').read_text(encoding='utf-8'))
for name, digest in m['files'].items():
    p = root/name
    if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest() != digest:
        raise SystemExit('Integrity failure: '+name)
print('PASS',len(m['files']),'files; algorithm',m['algorithm'])
'''


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run', type=Path, required=True)
    ap.add_argument('--analysis', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--runtime', nargs='*', type=Path, default=[])
    ap.add_argument('--reports', nargs='*', type=Path, default=[])
    args = ap.parse_args()
    verify(); official()
    from singlecore_evaluate import build_singlecore_plan
    from stub_multicore_cut_and_schedule import derive_multicore_plan
    from evaluation_validation import validate_task_order
    root = args.output
    root.mkdir(parents=True, exist_ok=False)
    for path in (ROOT / '程序').rglob('*'):
        if path.is_file() and path.suffix in {'.py', '.json', '.md'} and '__pycache__' not in path.parts:
            target = root / '程序' / path.relative_to(ROOT / '程序')
            target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(path, target)
    shutil.copytree(PROCESSED, root / '数据/processed/q1', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    (root / '用户数据').mkdir()
    if sha(DEFAULT_ZIP.read_bytes()) != verify()['source_sha256']:
        raise ValueError('Original attachment ZIP hash mismatch')
    shutil.copy2(DEFAULT_ZIP, root / '用户数据' / DEFAULT_ZIP.name)
    shutil.copytree(args.run / 'source_snapshot', root / 'frozen_v18')
    (root / 'results').mkdir()
    with (args.analysis / 'all_case_results.csv').open(encoding='utf-8-sig', newline='') as f:
        rows = [r for r in csv.DictReader(f) if r['config'] in {'fixed_single', 'shared_region'}]
    if len(rows) != 500 or len({(r['case'], r['cores']) for r in rows}) != 500:
        raise ValueError('Expected exactly 100 cases x 5 cores')
    with (root / 'results/all_case_results.csv').open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    write_json(root / 'results/mean_speedup.json', {str(n): mean(float(r['speedup']) for r in rows if int(r['cores']) == n) for n in range(1, 6)})
    shutil.copy2(args.run / 'summary.json', root / 'results/frozen_summary.json')
    indexed_rows = {(r['case'], int(r['cores'])): r for r in rows}
    for case in [f'case_{i:03d}' for i in range(1, 101)]:
        raw = json.loads((PROCESSED / 'data' / (case + '.json')).read_text(encoding='utf-8-sig'))
        for n in range(1, 6):
            folder = root / 'solutions' / f'{n}cores'; folder.mkdir(exist_ok=True, parents=True)
            if n == 1:
                plan = build_singlecore_plan(raw)
                source_folder = args.run / case / 'single'
            else:
                source_folder = args.run / case / f'{n}cores_shared_region'
                plan = json.loads((source_folder / 'plan.json').read_text(encoding='utf-8'))
            validate_task_order(derive_multicore_plan(raw, plan))
            old = json.loads((source_folder / 'row.json').read_text(encoding='utf-8'))
            csv_row = indexed_rows[case, n]
            for field in ['makespan', 'added_copy_bytes']:
                if int(csv_row[field]) != old[field]:
                    raise ValueError('CSV does not match frozen result: ' + str((case, n, field)))
            write_json(folder / (case + '_multicore_res.json'), plan)
    for name in ['mean_speedup.png', 'mean_speedup.pdf', 'figure_provenance.json']:
        shutil.copy2(args.analysis / name, root / 'results' / name)
    for path in args.runtime:
        dest = root / 'runtime' / path.name
        shutil.copytree(path, dest, ignore=shutil.ignore_patterns('*_search.json'))
    for path in args.reports:
        (root / 'documentation').mkdir(exist_ok=True)
        shutil.copy2(path, root / 'documentation' / path.name)
    (root / 'README.md').write_text(GUIDE, encoding='utf-8')
    (root / 'verify_package.py').write_text(VERIFY, encoding='utf-8')
    files = {p.relative_to(root).as_posix(): sha(p.read_bytes()) for p in sorted(root.rglob('*')) if p.is_file()}
    write_json(root / 'package_manifest.json', dict(algorithm='shared_region', files=files,
        original_summary_sha256=sha((args.run / 'summary.json').read_bytes()),
        official_source_zip_sha256=verify()['source_sha256']))
    archive = root.with_suffix('.zip')
    if archive.exists():
        raise FileExistsError(archive)
    with ZipFile(archive, 'w', ZIP_DEFLATED, compresslevel=6) as z:
        for path in sorted(root.rglob('*')):
            if path.is_file():
                z.write(path, root.name + '/' + path.relative_to(root).as_posix())
    write_json(root.with_name(root.name + '-archive.json'), dict(file=archive.name, bytes=archive.stat().st_size,
                                                               sha256=sha(archive.read_bytes())))
    print(archive)


if __name__ == '__main__':
    main()
