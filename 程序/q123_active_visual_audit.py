"""Run unchanged visual auditor on the active TeX input closure only.

The upstream scanner visits inactive historical .tex files and resolves assets
relative to chapter folders, unlike XeLaTeX's manuscript working directory.
Keep the original failed broad report; explicitly audit a flattened active source.
"""
import json,re,shutil,subprocess,sys,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
base=ROOT/'论文';out=ROOT/'_tmp/active-paper-audit';(out/'论文').mkdir(parents=True,exist_ok=True)
seen=[]
def expand(p):
    p=p.resolve();seen.append(p);s=p.read_text('utf-8')
    s=re.sub(r'\\ifgmcmaidisclosure\\input\{章节/B_ai_disclosure\}\\fi','',s)
    s=re.sub(r'(?m)(?<!\\)%.*$','',s)
    def inc(m):
        path=(base/m[1]);path=path if path.suffix else path.with_suffix('.tex')
        return expand(path)
    s=re.sub(r'\\input\{([^}]+)\}',inc,s)
    def asset(m):
        path=(base/m[2]).resolve();assert path.exists(),path
        return r'\includegraphics'+m[1]+'{'+path.as_posix()+'}'
    return re.sub(r'\\includegraphics(\[[^]]*\])?\{([^}]+)\}',asset,s)
text=expand(base/'论文正文.tex');(out/'论文/active.tex').write_text(text,encoding='utf-8')
shutil.copyfile(base/'数模论文.pdf',out/'论文/数模论文.pdf')
p=subprocess.run([sys.executable,str(ROOT/'工具/rendered_visual_audit.py'),'--workspace',str(out),'--strict'],capture_output=True)
dest=ROOT/'审查/证据/20260926-active-paper';dest.mkdir(parents=True,exist_ok=True)
for name in ['visual_qa.json','visual_qa.md']:shutil.copyfile(out/'图表'/name,dest/name)
record={'scope':'active XeLaTeX input closure; inactive archives excluded; assets resolved using actual compilation cwd','source_sha256':{str(x.relative_to(ROOT)):hashlib.sha256(x.read_bytes()).hexdigest() for x in seen},'pdf_sha256':hashlib.sha256((base/'数模论文.pdf').read_bytes()).hexdigest(),'tool_sha256':hashlib.sha256((ROOT/'工具/rendered_visual_audit.py').read_bytes()).hexdigest(),'exitcode':p.returncode}
(dest/'scope.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
print(p.stdout.decode('utf-8','replace'));raise SystemExit(p.returncode)
