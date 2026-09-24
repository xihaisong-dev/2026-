"""Package the current Q1 delivery, including complete saved evaluation evidence."""
import shutil, json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from q1_io import ROOT, PROCESSED, DEFAULT_ZIP, verify, sha, write_json
from q1_package import VERIFY

def main():
    verify()
    out=ROOT/'output/q1-delivery-r02-20260924-portable'
    out.mkdir(parents=True,exist_ok=False)
    for p in (ROOT/'程序').rglob('*'):
        if p.is_file() and p.suffix in {'.py','.json','.md'} and '__pycache__' not in p.parts:
            d=out/'程序'/p.relative_to(ROOT/'程序');d.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,d)
    shutil.copytree(PROCESSED,out/'数据/processed/q1',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    (out/'用户数据').mkdir();shutil.copy2(DEFAULT_ZIP,out/'用户数据'/DEFAULT_ZIP.name)
    delivery=ROOT/'图表/runs/20260924-A-q1-delivery-r02'
    shutil.copytree(delivery,out/'results')
    frozen=ROOT/'图表/runs/20260924-A-q1-event-ranking-full100'
    # Keep raw evaluations and exact frozen solver source; historical comparisons stay in repository.
    shutil.copytree(frozen/'source_snapshot',out/'evidence/source_snapshot')
    for folder in sorted(frozen.glob('case_*cores_seed0_routes_gate_reuse')):
        d=out/'evidence'/folder.name;d.mkdir()
        for name in ['plan.json','search.json','verification.json','verification_reuse.json']:
            if (folder/name).exists():shutil.copy2(folder/name,d/name)
    for row in (frozen/'single').glob('*/row.json'):
        dest=out/'evidence/single'/row.parent.name;dest.mkdir(parents=True,exist_ok=True);shutil.copy2(row,dest/'row.json')
    (out/'figures').mkdir()
    for p in (ROOT/'图表').glob('fig_q1_r02_*'):shutil.copy2(p,out/'figures'/p.name)
    (out/'documentation').mkdir()
    for name in ['问题一交付与赛题要求核对_r02.md','问题一端到端耗时核查_r02.md']:
        shutil.copy2(ROOT/'审查'/name,out/'documentation'/name)
    guide='''# 问题一当前交付 r02

采用 routes_gate_reuse，种子0，每配置12次评价机会；100图、固定配置、1～5核。
求解仅依赖 Python >=3.10 标准库（本次 Python 3.14.6）；绘图另需 matplotlib。
解压后在本目录运行，输出目录必须不存在：

```text
python verify_package.py
python 程序/q1_submit.py 数据/processed/q1/data/case_001.json -n 5 --output trial --verify-final
python 程序/q1_reproduce.py --cases case_001 --output trial-five --workers 1
python 程序/q1_reproduce.py --output all100 --workers 2
```

先完整校验，后计算。输入和官方源码SHA由数据清单校验。
默认counter后端是官方语义等价的实现加速；--backend official 可用原实现复核。
--verify-final 为额外原实现复核，可能耗时很长。不能把其开销隐藏到搜索时间中。
单图入口包含冷单核生成；批量入口每图只生成一次固定基准、供2～5核复用。
results/solutions 的500份文件只含官方方案字段；其中100份为整图单核基准。
results/all_case_results.csv 是500条历史冻结评价结果；不是打包时重算成绩。
完整评价时间线位于仓库图表/runs/20260924-A-q1-event-ranking-full100；本便携包保留方案、搜索和复核来源，CSV记录评价文件SHA，未重复携带全部时间线。
正文用平均(T1/Tk)，附录列cycles和额外搬运bytes；总周期仅补充说明。
目标先减Makespan，同周期时优先少搬运，不修改单核基准、不逐case拼接不同算法。
详见documentation的要求核对与耗时限制。此包供问题一复现和写作，不是整篇论文最终验收。
'''
    (out/'README.md').write_text(guide,encoding='utf-8')
    (out/'verify_package.py').write_text(VERIFY,encoding='utf-8')
    write_json(out/'package_manifest.json',dict(algorithm='routes_gate_reuse',source_evidence_commit='4d693a2efa5a1f4373a0f553789bf324115481aa',files={p.relative_to(out).as_posix():sha(p.read_bytes()) for p in sorted(out.rglob('*')) if p.is_file()}))
    archive=out.with_suffix('.zip')
    if archive.exists():raise FileExistsError(archive)
    with ZipFile(archive,'w',ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(out.rglob('*')):
            if p.is_file():z.write(p,out.name+'/'+p.relative_to(out).as_posix())
    write_json(ROOT/'output/q1-delivery-r02-20260924-portable-archive.json',dict(file=archive.name,bytes=archive.stat().st_size,sha256=sha(archive.read_bytes())))
    print(archive)
if __name__=='__main__':main()
