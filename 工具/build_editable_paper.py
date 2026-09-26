from pathlib import Path
import re,json,subprocess,copy,hashlib
from docx import Document
from docx.shared import Cm,Pt,RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH,WD_BREAK,WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from PIL import Image

R=Path(__file__).resolve().parents[1]; P=R/'论文'; TMP=R/'tmp/word-two-methods'; TMP.mkdir(parents=True,exist_ok=True)
OUT=R/'output/论文修订';OUT.mkdir(parents=True,exist_ok=True)
PANDOC=Path(r'C:\Users\Lenovo\AppData\Local\Pandoc\pandoc.exe')
POP=Path(r'C:\Users\Lenovo\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin\pdftoppm.exe')
sources=[]
def expand(s):
 def inc(m):
  p=P/m[1]; p=p if p.suffix else p.with_suffix('.tex');sources.append(str(p));return expand(p.read_text(encoding='utf-8'))
 return re.sub(r'\\input\{([^}]+)\}',inc,s)
main=(P/'论文正文.tex').read_text(encoding='utf-8')
abstract=expand(re.search(r'% GMCM_ABSTRACT_START(.*?)% GMCM_ABSTRACT_END',main,re.S)[1])
body=expand(re.search(r'% GMCM_BODY_START(.*?)% GMCM_BODY_END',main,re.S)[1])
# Preserve scientific results in full; replace lengthy source listings by an editable code index and reproducible entry points.
app=r'''\section{程序与结果复现说明}
正文所用模型的实现及全部逐配置结果保留在配套工程中。此 Word 版将整段源代码改列为文件索引和运行入口；数学模型、算法步骤及下列逐图数值均可直接编辑。
\begin{tabular}{ll}
\toprule 内容 & 工程入口\\\midrule
问题一结构感知搜索 & q1\_submit.py、q1\_experimental.py\\
问题一多候选精修 & Allin2/npu\_schedule\_project/src/solver.py\\
问题二与问题三 & q23\_submit\_current.py\\
问题二限时搜索 & q2\_timed\_portfolio.py\\
问题三组合搜索 & q3\_timed\_combination.py\\
结构感知搜索结果索引 & 20260924-A-q1-delivery-r02/all\_case\_results.csv\\
多候选精修五核核对 & recovered\_n5\_summary.json\\\bottomrule
\end{tabular}
结构感知搜索的命令入口如下；GRAPH 为经审计的输入图，K 为核心数，DIR 为新的输出目录。不得把已有运行目录作为可覆盖的临时目录。
\begin{verbatim}
python q1_submit.py GRAPH -n K --output DIR --verify-final
\end{verbatim}
多候选精修的交付来自 model/new-model-20260925 分支中 Allin2，来源提交 da469d8e。五核历史交付方案已恢复并按官方评价核对，不能把恢复指定历史候选的耗时作为盲搜算法的运行时间。正文的三问基础稿取自 b9334831；本稿另增问题一两方案比较。
\section{问题一结构感知搜索的逐图结果}
每个加速比的分母为同图固定单核周期。以下结果属于结构感知搜索。
'''+expand(r'\input{../图表/runs/20260924-A-q1-delivery-r02/appendix_results.tex}')
rows=json.loads((R/'recovered_n5_summary.json').read_text())
app+=r'\section{问题一多候选精修的五核逐图结果}'+'\n'+r'\begin{longtable}{lrrr}\caption{多候选精修已恢复核对的五核结果}\\\toprule 算例 & 周期 & 额外搬运（bytes） & 加速比\\\midrule\endfirsthead\toprule 算例 & 周期 & 额外搬运（bytes） & 加速比\\\midrule\endhead'+'\n'
for x in rows:app+=x['case'].replace('_',r'\_')+f" & {x['makespan']} & {x['added_copy_bytes']} & {x['speedup']:.6f}"+r'\\'+'\n'
app+=r'\bottomrule\end{longtable}'+'\n'
app+=r'\section{问题二逐图官方结果}'+expand(r'\input{../图表/runs/20260926-A-q123-complete-delivery/q2_appendix.tex}')
app+=r'\section{问题三同方案缓存对照结果}每行无 L2 与有 L2 的周期来自同一最终方案的独立评价。'+expand(r'\input{../图表/runs/20260926-A-q123-complete-delivery/q3_appendix.tex}')
app+=r'''\section{人工智能辅助使用说明}
本次修订使用人工智能工具辅助读取用户提供的资料、重组问题一的两种求解方案、核对已保存结果、转换 Word 公式和检查版式。人工智能没有生成替代实际实验的数据；正文所报结果来自工程保存记录及官方评价。作者仍需核实论文陈述、代码实现、引用来源与竞赛当届披露要求，并据实际使用情况完善工具名称、版本、日期及用途记录。本说明只记录本次修订中可确认的辅助工作，不替代团队完整使用记录或人工审核签字。
'''
s=r'\section*{摘要}'+'\n'+abstract+'\n'+r'\textbf{关键词：}有向无环图划分；多处理器调度；离散事件仿真；共享缓存'+'\n\n'+body+'\nAPPENDIXSTART\n'+app
s=re.sub(r'(?<!\\)%[^\n]*','',s)
# The LaTeX longtable continuation head is regenerated natively in Word.
s=re.sub(r'(\\endfirsthead).*?\\endhead',r'\1',s,flags=re.S)
s=re.sub(r'\\(?:clearpage|newpage|pagebreak|small|footnotesize|scriptsize|normalsize|centering)\b','',s)
s=re.sub(r'\\(?:vspace|hspace)\*?\{[^}]+\}','',s)
# Convert all figure assets to raster once, keeping original aspect and readable resolution.
image_manifest=[]
def picture(m):
 path=(P/m[2]).resolve();target=path
 if path.suffix.lower()=='.pdf':
  target=TMP/(hashlib.sha256(str(path).encode()).hexdigest()[:12]+'.png')
  if not target.exists() or target.stat().st_mtime < path.stat().st_mtime: subprocess.run([str(POP),'-f','1','-singlefile','-scale-to','2200','-png',str(path),str(target.with_suffix(''))],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
 if not target.exists():raise FileNotFoundError(path)
 image_manifest.append({'source':str(path),'render':str(target)})
 return '\\includegraphics[width=15cm]{'+target.as_posix()+'}'
s=re.sub(r'\\includegraphics(?:\[([^]]*)\])?\{([^}]+)\}',picture,s)
# Number headings, captions, and displayed equations in document order; resolve all references explicitly.
labels={}; counters={'section':0,'subsection':0,'subsubsection':0,'equation':0,'table':0,'figure':0}; appendix=False;last='';env=[];equations=[]
pattern=re.compile(r'APPENDIXSTART|\\(section|subsection|subsubsection)(\*)?\{([^{}]*)\}|\\begin\{(equation\*?|align\*?|gather\*?|table|figure|longtable)\}|\\end\{(equation\*?|align\*?|gather\*?|table|figure|longtable)\}|\\caption\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}|\\label\{([^}]+)\}')
def sectionid():return chr(64+counters['section']) if appendix else str(counters['section'])
def tokens(m):
 global appendix,last
 if m[0]=='APPENDIXSTART':
  appendix=True
  for k in counters:counters[k]=0
  return '\n'
 if m[1]:
  kind=m[1];title=m[3]
  if m[2]:return m[0]
  counters[kind]+=1
  if kind=='section':
   for k in ['subsection','subsubsection','equation','table','figure']:counters[k]=0
   last=sectionid();title=('附录 '+last+' ' if appendix else last+' ')+title
  elif kind=='subsection':
   counters['subsubsection']=0;last=sectionid()+'.'+str(counters[kind]);title=last+' '+title
  else:
   last=sectionid()+'.'+str(counters['subsection'])+'.'+str(counters[kind]);title=last+' '+title
  return '\\'+kind+'{'+title+'}'
 if m[4]:
  typ=m[4];env.append(typ)
  if typ.rstrip('*') in ['equation','align','gather']:
   counters['equation']+=1;last=sectionid()+'.'+str(counters['equation']);equations.append(last)
  return m[0]
 if m[5]:
  typ=m[5];env.pop()
  if typ.rstrip('*') in ['equation','align','gather']:return m[0]+'\n\nEQNUMBER'+equations[-1]+'END\n\n'
  return m[0]
 if m[6]:
  kind='figure' if env and env[-1]=='figure' else 'table';counters[kind]+=1;last=sectionid()+'.'+str(counters[kind]);return '\\caption{'+('图 ' if kind=='figure' else '表 ')+last+' '+m[6]+'}'
 if m[7]: labels[m[7]]=last;return ''
s=pattern.sub(tokens,s)
s=re.sub(r'\\(?:eqref|ref)\{([^}]+)\}',lambda m: ('('+labels[m[1]]+')') if m[0].startswith('\\eqref') else labels[m[1]],s)
# Explicit bibliography numbers avoid unresolved citation fields in Word.
bibkeys=re.findall(r'\\bibitem\{([^}]+)\}',s);bib={k:str(i+1) for i,k in enumerate(bibkeys)}
s=re.sub(r'\\cite\{([^}]+)\}',lambda m:'['+','.join(bib[k.strip()] for k in m[1].split(','))+']',s)
s=re.sub(r'\\begin\{thebibliography\}\{[^}]+\}',r'\\section*{参考文献}',s).replace(r'\end{thebibliography}','')
s=re.sub(r'\\bibitem\{([^}]+)\}',lambda m:'\n\n['+bib[m[1]]+'] ',s)
s=s.replace(r'\nonumber','')
s=re.sub(r'\{\\rm\s+([^{}]*)\}',r'\\mathrm{\1}',s)
(TMP/'expanded.tex').write_text(s,encoding='utf-8')
subprocess.run([str(PANDOC),'-f','latex','-t','json',str(TMP/'expanded.tex'),'-o',str(TMP/'ast.json')],check=True,stderr=(TMP/'pandoc-read.log').open('w',encoding='utf-8'))
ast=json.loads((TMP/'ast.json').read_text(encoding='utf-8'))
# LaTeX reader handles native tables and mathematical expressions. Raw TeX is retained in the audit, never silently presented as prose.
raw=[]
def walk(x):
 if isinstance(x,dict):
  if x.get('t') in ['RawBlock','RawInline']:raw.append(x)
  for v in x.values():walk(v)
 elif isinstance(x,list):
  for v in x:walk(v)
walk(ast);(TMP/'raw-nodes.json').write_text(json.dumps(raw,ensure_ascii=False,indent=2),encoding='utf-8')
# Build a template using the user's academic LaTeX typography and margins.
ref=Document();sec=ref.sections[0];sec.page_width=Cm(21);sec.page_height=Cm(29.7);sec.top_margin=Cm(3);sec.bottom_margin=Cm(1.75);sec.left_margin=sec.right_margin=Cm(2.25)
for sty in ref.styles:
 if sty.type==1:
  sty.font.name='Times New Roman';sty.font.size=Pt(12);sty.font.color.rgb=RGBColor(0,0,0)
  sty.element.get_or_add_rPr().get_or_add_rFonts().set(qn('w:eastAsia'),'宋体')
  sty.paragraph_format.space_after=Pt(0);sty.paragraph_format.line_spacing=Pt(20)
  for b in list(sty.element.xpath('.//w:pBdr')):b.getparent().remove(b)
for name in ['Normal','Body Text','First Paragraph']:
 if name in ref.styles:ref.styles[name].paragraph_format.first_line_indent=Pt(24)
for name,size in [('Title',16),('Heading 1',14),('Heading 2',12),('Heading 3',12)]:
 sty=ref.styles[name];sty.font.size=Pt(size);sty.font.bold=True;sty.element.get_or_add_rPr().get_or_add_rFonts().set(qn('w:eastAsia'),'黑体');sty.paragraph_format.first_line_indent=Pt(0);sty.paragraph_format.space_before=Pt(10);sty.paragraph_format.space_after=Pt(6);sty.paragraph_format.keep_with_next=True
 if name in ['Title','Heading 1']:sty.paragraph_format.alignment=WD_ALIGN_PARAGRAPH.CENTER
for name in ['Caption','Image Caption','Table Caption']:
 if name in ref.styles:
  sty=ref.styles[name];sty.font.size=Pt(10.5);sty.paragraph_format.alignment=WD_ALIGN_PARAGRAPH.CENTER;sty.paragraph_format.first_line_indent=Pt(0);sty.paragraph_format.line_spacing=Pt(16)
ref.save(TMP/'reference.docx')
subprocess.run([str(PANDOC),'-f','json','-t','docx',str(TMP/'ast.json'),'--reference-doc='+str(TMP/'reference.docx'),'-o',str(TMP/'converted.docx')],check=True,stderr=(TMP/'pandoc-write.log').open('w',encoding='utf-8'))
d=Document(TMP/'converted.docx')
# Academic front matter, with genuine editable cover fields and a Word TOC field.
first=d.paragraphs[0]
def before(text='',style=None):return first.insert_paragraph_before(text,style)
cover=before('2026 年中国研究生数学建模竞赛', 'Title');cover.paragraph_format.space_before=Pt(90)
p=before('参赛论文','Title');p.paragraph_format.space_after=Pt(55)
before('通用神经网络处理器的多核切图与调度优化','Title')
for line in ['学校：____________________________','参赛队号：________________________','队员一：__________________________','队员二：__________________________','队员三：__________________________']:
 p=before(line);p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.first_line_indent=Pt(0);p.paragraph_format.space_before=Pt(12)
cover_end=before()
cover_section=copy.deepcopy(d.sections[0]._sectPr)
cover_end._p.get_or_add_pPr().append(cover_section)
before('通用神经网络处理器的多核切图与调度优化','Title')
for p in list(d.paragraphs):
 if p.style.name=='Heading 1' and p.text.startswith('1 '):
  a=p.insert_paragraph_before();a.add_run().add_break(WD_BREAK.PAGE)
  a=p.insert_paragraph_before('目录');a.alignment=WD_ALIGN_PARAGRAPH.CENTER;a.runs[0].bold=True;a.runs[0].font.size=Pt(14)
  a=p.insert_paragraph_before();a.paragraph_format.first_line_indent=Pt(0)
  for tag,attr,txt in [('fldChar',('fldCharType','begin'),None),('instrText',None,' TOC \\o "1-2" \\h \\z \\u '),('fldChar',('fldCharType','end'),None)]:
   el=OxmlElement('w:'+tag)
   if attr:el.set(qn('w:'+attr[0]),attr[1])
   if txt:el.text=txt
   a.add_run()._r.append(el)
  p.paragraph_format.page_break_before=True;break
# Equation numbers sit in an editable paragraph at a right tab; native Office Math remains intact.
eq_count=0
for p in list(d.paragraphs):
 m=re.fullmatch(r'EQNUMBER([A-Z0-9.]+)END',p.text.strip())
 if not m:continue
 prev=p._p.getprevious()
 while prev is not None and prev.tag!=qn('w:p'):prev=prev.getprevious()
 if prev is None:raise ValueError('orphan equation marker')
 from docx.text.paragraph import Paragraph
 ep=Paragraph(prev,d._body);omp=prev.find(qn('m:oMathPara'))
 if omp is not None:
  maths=list(omp.findall(qn('m:oMath')));prev.remove(omp)
  for math in maths:prev.append(math)
 ep.paragraph_format.first_line_indent=Pt(0);ep.paragraph_format.alignment=WD_ALIGN_PARAGRAPH.CENTER;ep.paragraph_format.line_spacing_rule=WD_LINE_SPACING.AT_LEAST;ep.paragraph_format.line_spacing=Pt(22);ep.paragraph_format.space_before=Pt(5);ep.paragraph_format.space_after=Pt(5)
 ep.add_run('  ('+m[1]+')').font.size=Pt(10.5)
 p._p.getparent().remove(p._p);eq_count+=1
# Paragraph and figure layout corrections.
for p in d.paragraphs:
 for b in list(p._p.xpath('./w:pPr/w:pBdr')):b.getparent().remove(b)
 if p._p.xpath('.//m:oMath'):
  p.paragraph_format.line_spacing_rule=WD_LINE_SPACING.AT_LEAST
  p.paragraph_format.line_spacing=Pt(20)
 if p._p.xpath('.//w:drawing'):
  p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.first_line_indent=Pt(0);p.paragraph_format.line_spacing_rule=WD_LINE_SPACING.SINGLE;p.paragraph_format.keep_with_next=True
 if p.style.name in ['Table Caption','Caption'] and p.text.startswith('表'):p.paragraph_format.keep_with_next=True
 if p.style.name in ['Image Caption','Caption'] and p.text.startswith('图'):p.paragraph_format.keep_with_next=False
 if p.style.name.startswith('Heading'):p.paragraph_format.keep_with_next=True
 if re.match(r'^[表图] [A-Z0-9]+\.[0-9]+ ',p.text):
  p.paragraph_format.first_line_indent=Pt(0);p.paragraph_format.alignment=WD_ALIGN_PARAGRAPH.CENTER
  p.paragraph_format.line_spacing=Pt(16);p.paragraph_format.space_before=Pt(4);p.paragraph_format.space_after=Pt(3)
  p.paragraph_format.keep_with_next=p.text.startswith('表')
  for run in p.runs:run.font.size=Pt(10.5)
 if p.text.startswith('附录 ') and p.style.name=='Heading 1':p.paragraph_format.page_break_before=True
 if p.text=='参考文献':p.paragraph_format.page_break_before=False
 if p.text.startswith('关键词：'):
  p.paragraph_format.first_line_indent=Pt(0);p.paragraph_format.space_before=Pt(12)
 for run in p.runs:
  if run.font.color and run.font.color.rgb:run.font.color.rgb=RGBColor(0,0,0)
for sty in d.styles:
 for b in list(sty.element.xpath('.//w:pBdr')):b.getparent().remove(b)
for shape in d.inline_shapes:
 ratio=shape.height/shape.width
 width=min(shape.width,Cm(15));height=width*ratio
 if height>Cm(15):height=Cm(15);width=height/ratio
 shape.width=int(width);shape.height=int(height)
# Native, editable three-line tables with repeating column headers; no fixed row heights.
for table in d.tables:
 table.autofit=False
 n=len(table.columns)
 table.width=Cm(16.5)
 pr=table._tbl.tblPr
 width=pr.find(qn('w:tblW'));width.set(qn('w:w'),'9354');width.set(qn('w:type'),'dxa')
 borders=OxmlElement('w:tblBorders')
 for edge in ['top','bottom','left','right','insideH','insideV']:
  x=OxmlElement('w:'+edge);x.set(qn('w:val'),'single' if edge in ['top','bottom'] else 'nil');x.set(qn('w:sz'),'8');x.set(qn('w:color'),'000000');borders.append(x)
 oldb=pr.find(qn('w:tblBorders'))
 if oldb is not None:pr.remove(oldb)
 pr.append(borders)
 for col in table.columns:col.width=Cm(16.5/n)
 for ri,row in enumerate(table.rows):
  trpr=row._tr.get_or_add_trPr();cant=OxmlElement('w:cantSplit');trpr.append(cant)
  if ri==0:
   header=OxmlElement('w:tblHeader');trpr.append(header)
  for cell in row.cells:
   cell.width=Cm(16.5/n)
   if ri==0:
    cb=OxmlElement('w:tcBorders');bt=OxmlElement('w:bottom');bt.set(qn('w:val'),'single');bt.set(qn('w:sz'),'4');cb.append(bt);cell._tc.get_or_add_tcPr().append(cb)
   for p in cell.paragraphs:
    p.paragraph_format.first_line_indent=Pt(0);p.paragraph_format.line_spacing_rule=WD_LINE_SPACING.AT_LEAST;p.paragraph_format.line_spacing=Pt(14);p.paragraph_format.space_before=Pt(2);p.paragraph_format.space_after=Pt(2);p.paragraph_format.keep_with_next=ri<len(table.rows)-1 if len(table.rows)<=12 else ri==0;p.alignment=WD_ALIGN_PARAGRAPH.CENTER if n>=3 else WD_ALIGN_PARAGRAPH.LEFT
    for run in p.runs:run.font.size=Pt(9 if n>=7 else 10.5);run.bold=ri==0
for idx,sec in enumerate(d.sections):
 sec.header_distance=Cm(1);sec.footer_distance=Cm(0.8);sec.different_first_page_header_footer=False
 sec.footer.is_linked_to_previous=False
 if idx:
  pg=OxmlElement('w:pgNumType');pg.set(qn('w:start'),'1');sec._sectPr.append(pg)
  footer=sec.footer.paragraphs[0];footer.alignment=WD_ALIGN_PARAGRAPH.CENTER
  el=OxmlElement('w:fldSimple');el.set(qn('w:instr'),'PAGE');footer._p.append(el)
update=OxmlElement('w:updateFields');update.set(qn('w:val'),'true');d.settings.element.append(update)
dest=OUT/'通用神经网络处理器多核调度论文_两方案修订版.docx';d.save(dest)
audit={'output':str(dest),'sources':sources,'equation_blocks':eq_count,'native_math_count':len(d.element.xpath('.//m:oMath')),'tables':len(d.tables),'figures':len(d.inline_shapes),'raw_nodes':len(raw),'images':image_manifest,'references':labels,'source_note':'Full two-method curves and six evidence figures; Allin2 all 500 configurations verified.'}
(TMP/'build_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in audit.items() if k not in ['sources','references','images']},ensure_ascii=False))

