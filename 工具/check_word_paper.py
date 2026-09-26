from pathlib import Path
import json,re,hashlib,zipfile
from lxml import etree
from pypdf import PdfReader
from PIL import Image,ImageDraw
R=Path(__file__).resolve().parents[1];T=R/'tmp/word-two-methods';out=R/'output/论文修订';doc=out/'通用神经网络处理器多核调度论文_两方案修订版.docx'
ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main','m':'http://schemas.openxmlformats.org/officeDocument/2006/math'}
with zipfile.ZipFile(doc) as z:
 root=etree.fromstring(z.read('word/document.xml'));styles=etree.fromstring(z.read('word/styles.xml'))
 text=''.join(root.xpath('//w:t/text()',namespaces=ns))
 tables=root.xpath('//w:tbl',namespaces=ns)
 counts=[len(x.xpath('./w:tr',namespaces=ns)) for x in tables]
 math=len(root.xpath('//m:oMath',namespaces=ns))
 assert math==748,(math,'expected all 748 editable math objects')
 assert len(tables)==18
 assert sum(n-1 for n in counts if n>100)==1600,counts
 assert not re.search(r'\\(?:begin|frac|mathrm|eqref)|EQNUMBER|APPENDIXSTART',text)
 assert all(x in text for x in ['4.026824','3.665903','68905422','66 胜','13 负','2.25%'])
 assert not root.xpath('//w:pBdr',namespaces=ns) and not styles.xpath('//w:pBdr',namespaces=ns)
 for x in tables:
  assert x.xpath('./w:tr[1]/w:trPr/w:tblHeader',namespaces=ns)
pdf=PdfReader(T/'preview.pdf');texts=[p.extract_text() or '' for p in pdf.pages]
(T/'pages.txt').write_text('\n'.join(f'PAGE {i+1} '+x.replace('\n',' ')[:180] for i,x in enumerate(texts)),encoding='utf-8')
assert not any('Error! Reference' in x or '错误!未' in x for x in texts)
assert not any(not x.strip() for x in texts)
evidence=[]
for p in [doc,R/'recovered_n5_summary.json',P if False else R/'论文/两方案比较核对.json',Path(r'C:\Users\Lenovo\Documents\xwechat_files\wxid_96m882dry5c222_c816\msg\file\2026-09\学习.zip'),Path(r'C:\Users\Lenovo\Desktop\华为杯-数模\Latax模板\2026通用LaTeX模板-类内版\gmcmthesis.cls'),Path(r'C:\Users\Lenovo\Desktop\5年真题\已将看的优秀论文\2025A题_一等奖_中国石油大学(华东)_25104250018.pdf')]:
 evidence.append({'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
report={'docx':str(doc),'page_count':len(texts),'editable_math_objects':math,'numbered_display_equations':80,'editable_tables':len(tables),'table_row_counts':counts,'individual_result_records':1600,'conversion_warnings':(T/'pandoc-write.log').read_text(encoding='utf-8'),'equivalence':'100 five-core Allin2 results match recovered official makespan and added bytes; fixed single-core baseline matches scheme one for all 100 graphs','visual_review':'PENDING','formal_workflow_gates':'NOT_RUN; no stage status modified','evidence':evidence}
(out/'修订与核验记录.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
# Two pages per sheet at their full generated resolution, for complete visual inspection.
pages=sorted(T.glob('page-[0-9]*.png'))
if len(pages)==len(texts):
 for i in range(0,len(pages),2):
  images=[Image.open(p).convert('RGB') for p in pages[i:i+2]]
  board=Image.new('RGB',(sum(im.width for im in images),max(im.height for im in images)+32),'#dddddd');draw=ImageDraw.Draw(board);x=0
  for j,im in enumerate(images):board.paste(im,(x,32));draw.text((x+20,8),f'PDF PAGE {i+j+1}',fill='black');x+=im.width
  board.save(T/f'review-{i//2+1:02}.png')
print(json.dumps({k:v for k,v in report.items() if k not in ['evidence']},ensure_ascii=True))
