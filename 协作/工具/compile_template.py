"""Compile the GMCM template with XeLaTeX; no workflow state is advanced."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil
import subprocess
from datetime import datetime

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', choices=('preview', 'main'), default='preview')
    args = parser.parse_args()
    exe = shutil.which('xelatex')
    if not exe:
        raise SystemExit('XeLaTeX is missing from PATH. Install/configure a TeX distribution first.')
    source = ROOT / '模板/当前竞赛'
    run = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    build = ROOT / '_tmp/template-build' / run
    build.mkdir(parents=True)
    entry = source / 'main.tex'
    if args.source == 'preview':
        content = entry.read_text('utf-8')
        values = {'PaperTitle': '2026 模板排版示例（非参赛论文）',
                  'PaperKeywords': '排版示例；公式；表格；交叉引用',
                  'SchoolName': '排版测试用学校名称（非报名信息）',
                  'TeamNumber': '仅供测试', 'MemberOne': '姓名占位一',
                  'MemberTwo': '姓名占位二', 'MemberThree': '姓名占位三'}
        for key, value in values.items():
            content, count = re.subn(r'\\newcommand\{\\' + key + r'\}\{[^}]*\}',
                                    lambda m: '\\newcommand{\\'+key+'}{'+value+'}', content)
            if count != 1:
                raise SystemExit(f'Expected one template field: {key}')
        for part, path in [('ABSTRACT', 'demo/abstract'), ('BODY', 'demo/body')]:
            content, count = re.subn(r'% GMCM_'+part+r'_START.*?% GMCM_'+part+r'_END',
                                    lambda m: '\\input{'+path+'}', content, flags=re.S)
            if count != 1:
                raise SystemExit(f'Expected one preview insertion point: {part}')
        content = content.replace(r'\input{sections/A_code}', r'\input{demo/code}')
        entry = build / 'preview.tex'
        entry.write_text(content, encoding='utf-8')
    command = [exe, '-disable-installer', '-interaction=nonstopmode',
               '-halt-on-error', '-no-shell-escape', f'-output-directory={build}',
               str(entry)]
    # Repeated passes resolve labels, PDF links and longtable widths.
    for number in range(1, 4):
        result = subprocess.run(command, cwd=source, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=180)
        (build / f'pass-{number}.txt').write_bytes(result.stdout)
        if result.returncode:
            print(result.stdout.decode('utf-8', errors='replace')[-5000:])
            raise SystemExit(f'XeLaTeX failed; logs: {build}')
    log = (build / f'{args.source}.log').read_text('utf-8', errors='replace')
    fatal_patterns = [r'Overfull \\[hv]box', r'Missing character:',
                      r'There were undefined references', r'Citation .* undefined',
                      r'Reference .* undefined', r'Font shape .* undefined',
                      r'ignored error:', r'Label\(s\) may have changed']
    failures = [p for p in fatal_patterns if re.search(p, log)]
    if failures:
        raise SystemExit(f'Compile needs correction ({failures}); logs: {build}')
    output = ROOT / 'output/pdf'
    output.mkdir(parents=True, exist_ok=True)
    filename = '2026模板试编译.pdf' if args.source == 'preview' else '2026模板空白骨架.pdf'
    pdf = output / filename
    shutil.copy2(build / f'{args.source}.pdf', pdf)
    audit = ROOT / '审查/2026模板试编译'
    audit.mkdir(parents=True, exist_ok=True)
    shutil.copy2(build / f'{args.source}.log', audit / f'{args.source}-xelatex.txt')
    for suffix in ('aux',):
        shutil.copy2(build / f'{args.source}.{suffix}', audit / f'{args.source}-{suffix}.txt')
    record = {
        'scope': 'template_compile_only_not_contest_acceptance',
        'source': (source / 'main.tex').relative_to(ROOT).as_posix(), 'mode': args.source,
        'command': command, 'passes': 3, 'exit_code': 0,
        'output': pdf.relative_to(ROOT).as_posix(),
        'sha256': hashlib.sha256(pdf.read_bytes()).hexdigest(),
        'source_hashes': {p.relative_to(source).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in sorted(source.rglob('*')) if p.is_file()},
        'warning_lines': [line for line in log.splitlines() if 'Warning' in line],
        'visual_review': 'NOT_RUN', 'workflow_state_advanced': False,
    }
    (audit / f'{args.source}-编译记录.json').write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(f'Compiled: {pdf}\nLogs: {audit}\nVisual inspection remains required.')


if __name__ == '__main__':
    main()
