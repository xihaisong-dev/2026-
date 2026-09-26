from pathlib import Path
import re,json,csv
from docx import Document
from PIL import Image,ImageDraw
R=Path(__file__).resolve().parents[1];T=R/'tmp/word-two-methods';O=R/'output/论文修订'
d=Document(O/'通用神经网络处理器多核调度论文_两方案修订版.docx')
data=[t for t in d.tables if len(t.rows)>100]
def actual(t):return [[c.text.strip() for c in row.cells] for row in t.rows[1:]]
def expected(p):
 rows=[]
 for line in p.read_text(encoding='utf-8').splitlines():
  if not re.match(r'(?:case\\_\d+|\d+)\s*&',line):continue
  line=line.rstrip().rstrip('\\').strip();rows.append([v.strip().replace(r'\_','_') for v in line.split('&')])
 return rows
sources=[R/'图表/runs/20260924-A-q1-delivery-r02/appendix_results.tex',None,R/'图表/runs/20260926-A-q123-complete-delivery/q2_appendix.tex',R/'图表/runs/20260926-A-q123-complete-delivery/q3_appendix.tex']
for idx,p in enumerate(sources):
 a=actual(data[idx])
 if p:e=expected(p)
 else:e=[[r['case'],str(r['makespan']),str(r['added_copy_bytes']),f"{r['speedup']:.6f}"] for r in json.loads((R/'recovered_n5_summary.json').read_text())]
 assert a==e,[(i,x,y) for i,(x,y) in enumerate(zip(a,e)) if x!=y][:3]
# Verify Q1 scheme-one appendix independently against its CSV, not just against the TeX export.
csvrows=list(csv.DictReader((R/'图表/runs/20260924-A-q1-delivery-r02/all_case_results.csv').open(encoding='utf-8-sig')))
assert actual(data[0])==[[r['case'],r['cores'],r['makespan'],r['added_copy_bytes'],f"{float(r['speedup']):.6f}"] for r in csvrows]
pages=sorted(T.glob('final-page-*.png'))
assert len(pages)==96
for i in range(0,len(pages),4):
 ims=[Image.open(p).convert('RGB') for p in pages[i:i+4]];w,h=ims[0].size
 board=Image.new('RGB',(2*w,2*(h+25)),'#dddddd');draw=ImageDraw.Draw(board)
 for j,im in enumerate(ims):
  x=(j%2)*w;y=(j//2)*(h+25);board.paste(im,(x,y+25));draw.text((x+15,y+6),f'FINAL PAGE {i+j+1}',fill='black')
 board.save(T/f'final-review-{i//4+1:02}.png')
rep=json.loads((O/'修订与核验记录.json').read_text(encoding='utf-8'));rep['data_table_verification']='1600/1600 editable Word result rows match source records exactly; Q1 scheme-one rows also match CSV independently.'
(O/'修订与核验记录.json').write_text(json.dumps(rep,ensure_ascii=False,indent=2),encoding='utf-8')
print('Verified all 1600 result records. Final review sheets:',len(pages)//4)
