"""Portable Q2 source, audited input, migration seeds and selected evidence."""
import shutil
from zipfile import ZipFile, ZIP_DEFLATED
from q1_io import ROOT, PROCESSED, verify, sha, write_json
from q1_package import VERIFY
from q2_full_campaign import OUT, Q1, read


def main():
    verify();assert read(OUT/'full_audit.json')['results']==800
    dest=ROOT/'output/q2-r05-portable';assert not dest.exists();dest.mkdir(parents=True)
    for p in (ROOT/'程序').glob('*.py'):
        d=dest/p.relative_to(ROOT);d.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,d)
    shutil.copytree(PROCESSED,dest/PROCESSED.relative_to(ROOT),ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    shutil.copytree(Q1,dest/Q1.relative_to(ROOT))
    for p in [OUT/'summary.json',OUT/'contract.json',OUT/'full_audit.json',OUT/'all_rows.csv',OUT/'paired.csv']:
        d=dest/p.relative_to(ROOT);d.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,d)
    shutil.copytree(OUT/'delivery',dest/(OUT/'delivery').relative_to(ROOT))
    guide='''# 问题二 r05 可复现附件

Python 3.12.14，求解仅标准库。先运行 `python verify_package.py`。
在本目录中复现（输出目录必须不存在）：

```text
python 程序/q2_r05_submit.py 数据/processed/q1/data/case_001.json -n 2 --migration 图表/runs/20260924-A-q1-delivery-r02/solutions/2cores/case_001_multicore_res.json --output trial-001-2
```

核数支持1至5；单核不传迁移计划，使用规定整图基准。
省略--migration可直接从原图运行：先按冻结Q1算法生成种子（额外12次A评价机会），然后执行12次B机会；生成耗时和搜索轨迹单独保存。传入--migration则复现本次共同预生成种子的对照。两对照方案使用同一种子；B下重新评分，没有借用A的多核成绩。程序读取summary.json选择全量统一算法，不按用例事后选优。
每配置12次B机会，重复命中也占机会，额外最终官方B回放另计。run.json记录包括冷单核、搜索和回放的进程内耗时；省略--migration时也包括本次种子生成。
本包带全部种子与其生成源码；论文必须说明这种输入约定，不能声称搜索秒数是从原图生成种子的完整耗时。
400份标准文件、500行指标、正文图及附录接口位于图表/runs/20260924-A-q2-full-r05/delivery。
完整800份时间线保留在仓库同一运行目录cases，便携包省略时间线，full_audit.json保留其哈希。
官方B代码逐字节保持原始附件版本。单核使用已验证的等价计数后端，仅用于规定分母。
绘图另需matplotlib和中文字体；重新绘图须新输出目录。此包是计算附件，正式论文排版和人工验收另行进行。
'''
    (dest/'README.md').write_text(guide,encoding='utf-8');(dest/'verify_package.py').write_text(VERIFY,encoding='utf-8')
    write_json(dest/'package_manifest.json',dict(problem=2,algorithm=read(OUT/'summary.json')['selected_global_algorithm'],files={p.relative_to(dest).as_posix():sha(p.read_bytes()) for p in dest.rglob('*') if p.is_file()}))
    archive=dest.with_suffix('.zip');assert not archive.exists()
    with ZipFile(archive,'w',ZIP_DEFLATED,compresslevel=6) as z:
        for p in dest.rglob('*'):
            if p.is_file():z.write(p,dest.name+'/'+p.relative_to(dest).as_posix())
    write_json(archive.with_suffix('.archive.json'),dict(path=archive.relative_to(ROOT).as_posix(),sha256=sha(archive.read_bytes()),bytes=archive.stat().st_size))
    print(archive)


if __name__=='__main__':main()
