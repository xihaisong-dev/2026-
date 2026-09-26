from pathlib import Path
import sys
R=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(R/'tmp/figure-supplement/deps'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle,Patch
import json,csv,hashlib,xml.etree.ElementTree as ET
import numpy as np
O=R/'图表/runs/20260926-A-six-figures'
plt.rcParams.update({'font.family':'Microsoft YaHei','font.size':11.5,'axes.unicode_minus':False,'pdf.fonttype':42,'svg.fonttype':'none','axes.spines.top':False,'axes.spines.right':False,'axes.linewidth':0.7,'lines.linewidth':1.6,'savefig.facecolor':'white'})
BLUE='#356D9D';ORANGE='#BD6B3B';GRAY='#555555';PALE='#EAF1F7';LIGHT='#F7EEE7'
meta=[]
def save(fig,name,claim,source,task):
 fig.savefig(O/(name+'.pdf'),bbox_inches='tight',pad_inches=.045)
 fig.savefig(O/(name+'.png'),dpi=300,bbox_inches='tight',pad_inches=.045)
 fig.savefig(O/(name+'.svg'),bbox_inches='tight',pad_inches=.045)
 (O/(name+'.visual.json')).write_text(json.dumps({'minimum_effective_font_pt':9.5,'review_required':True,'source_font_pt':11.5,'intended_width_cm':15,'claim':claim},ensure_ascii=False,indent=2),encoding='utf-8')
 meta.append(dict(path=str((O/(name+'.pdf')).relative_to(R)).replace('\\','/'),claim=claim,source=source,reader_task=task,publish=True,placement='body'))
 plt.close(fig)
class Diagram:
 def __init__(self,h):
  self.fig,self.ax=plt.subplots(figsize=(6.2,h));self.ax.set(xlim=(0,100),ylim=(0,100));self.ax.axis('off');self.nodes=[];self.edges=[]
 def box(self,x,y,w,h,text,color=PALE):
  self.ax.add_patch(Rectangle((x,y),w,h,facecolor=color,edgecolor=GRAY,lw=.8))
  self.ax.text(x+w/2,y+h/2,text,ha='center',va='center',fontsize=11.5,linespacing=1.6)
  self.nodes.append((x,y,w,h,text,color))
 def text(self,x,y,s,**kw):self.ax.text(x,y,s,ha=kw.pop('ha','center'),va='center',**kw)
 def arrow(self,x,y,xx,yy,c=GRAY):
  self.ax.annotate('',xy=(xx,yy),xytext=(x,y),arrowprops=dict(arrowstyle='->',lw=1,color=c));self.edges.append((x,y,xx,yy,c))
 def drawio(self,name):
  mx=ET.Element('mxfile');d=ET.SubElement(mx,'diagram',name='Page-1');model=ET.SubElement(d,'mxGraphModel',pageWidth='900',pageHeight='900');root=ET.SubElement(model,'root');ET.SubElement(root,'mxCell',id='0');ET.SubElement(root,'mxCell',id='1',parent='0')
  for i,(x,y,w,h,t,c) in enumerate(self.nodes):
   cell=ET.SubElement(root,'mxCell',id=f'n{i}',value=t,style=f'rounded=0;whiteSpace=wrap;html=0;fillColor={c};strokeColor=#555555;fontFamily=Microsoft YaHei;fontSize=16;',vertex='1',parent='1');ET.SubElement(cell,'mxGeometry',x=str(x*8),y=str((100-y-h)*8),width=str(w*8),height=str(h*8),attrib={'as':'geometry'})
  for i,(x,y,xx,yy,c) in enumerate(self.edges):
   cell=ET.SubElement(root,'mxCell',id=f'e{i}',style=f'endArrow=classic;strokeColor={c};',edge='1',parent='1');g=ET.SubElement(cell,'mxGeometry',relative='1',attrib={'as':'geometry'});ET.SubElement(g,'mxPoint',x=str(x*8),y=str((100-y)*8),attrib={'as':'sourcePoint'});ET.SubElement(g,'mxPoint',x=str(xx*8),y=str((100-yy)*8),attrib={'as':'targetPoint'})
  # All free labels are also retained as editable drawio cells.
  for i,t in enumerate(self.ax.texts):
   if not t.get_text() or t.get_text() in [n[4] for n in self.nodes]:continue
   x,y=t.get_position();cell=ET.SubElement(root,'mxCell',id=f't{i}',value=t.get_text(),style='text;html=0;align=center;verticalAlign=middle;whiteSpace=wrap;fontFamily=Microsoft YaHei;fontSize=16;',vertex='1',parent='1');ET.SubElement(cell,'mxGeometry',x=str(x*8-140),y=str((100-y)*8-20),width='280',height='40',attrib={'as':'geometry'})
  ET.ElementTree(mx).write(O/(name+'.drawio'),encoding='utf-8',xml_declaration=True)
# 1: same dependency P -> Q and P -> R; rows isolate physical rules.
d=Diagram(5.1)
for y,head in [(83,'(a) 场景 A：跨子图经 DDR'),(51,'(b) 场景 B：同核可驻留'),(19,'(c) 场景 B + 共享只读 L2')]:
 d.text(50,y+13,head)
 d.box(1,y-4,17,9,'P（核 0）');d.box(80,y+2,19,9,'Q（核 0）');d.box(80,y-12,19,9,'R（核 1）')
 if y==83:
  d.box(35,y-5,23,10,'共享 DDR','#F1F1F1');d.arrow(18,y,35,y);d.arrow(58,y+1,80,y+6);d.arrow(58,y-1,80,y-8)
  # Detail is explained in the caption to keep panels separated.
 elif y==51:
  d.box(35,y-10,23,9,'共享 DDR','#F1F1F1');d.arrow(18,y+3,80,y+6,BLUE);d.text(49,y+7,'驻留复用',fontsize=10.5,color=BLUE)
  d.arrow(18,y-1,35,y-6);d.arrow(58,y-6,80,y-8)
 else:
  d.box(35,y-18,23,9,'DDR','#F1F1F1');d.box(35,y-6,23,9,'FIFO L2',LIGHT)
  d.arrow(18,y-1,35,y-14);d.arrow(58,y-2,80,y-8,ORANGE);d.arrow(58,y-14,80,y-8);d.arrow(46,y-9,46,y-6)
  d.arrow(18,y+4,80,y+6,BLUE)
d.drawio('fig_scene_paths');save(d.fig,'fig_scene_paths','同一依赖关系在三种场景采用不同数据服务路径。','论文章节3a_common、5a_q1_model、6a_q2_model、7a_q3_fifo_derivation','区分驻留、中转与只读缓存机制')
# 2: paired algorithms, common bottom validation, no false dominance claim.
d=Diagram(4.8)
d.box(25,86,50,11,'输入 DAG 与硬件约束','#F1F1F1');d.arrow(38,86,24,79);d.arrow(62,86,76,79)
d.text(24,77,'结构感知搜索',color=BLUE,fontweight='bold');d.text(76,77,'多候选精修',color=ORANGE,fontweight='bold')
left=['分量、共享输入与拓扑结构','初解与合法空隙插入','有界边界、映射、顺序修复'];right=['粗细窗口、主链、容量划分','基础与前瞻列表调度','五核迁移、交换与顺序精修']
for j,(a,b) in enumerate(zip(left,right)):
 y=60-j*17;d.box(1,y,46,12,a,PALE);d.box(53,y,46,12,b,LIGHT)
 if j<2:d.arrow(24,y,24,y-5);d.arrow(76,y,76,y-5)
d.arrow(24,26,38,20);d.arrow(76,26,62,20);d.box(9,4,82,16,'完整候选逐一检查覆盖与无环性\n官方事件仿真 → 按周期、搬运量选优','#F1F1F1')
d.drawio('fig_q1_algorithms');save(d.fig,'fig_q1_algorithms','共同模型下的两条候选生成与改进路线。','论文章节5_problem1、5b_q1_algorithm、5e_q1_second_method','比较两种方法的组成和共同评价原则')
# 3-4: paired source statistics.
def csvread(p):return list(csv.DictReader(p.open(encoding='utf-8-sig')))
a=csvread(R/'图表/runs/20260924-A-q1-delivery-r02/all_case_results.csv');b=csvread(R/'output/allin2-q1-complete-20260926/all_case_results.csv')
stat=[]
for k in range(1,6):
 aa=[r for r in a if int(r['cores'])==k];bb=[r for r in b if int(r['cores'])==k]
 assert len(aa)==len(bb)==100
 stat.append(dict(cores=k,structure_mean=sum(float(r['speedup']) for r in aa)/100,candidate_mean=sum(float(r['speedup']) for r in bb)/100,structure_cycles=sum(int(r['makespan']) for r in aa),candidate_cycles=sum(int(r['makespan']) for r in bb)))
(O/'q1_curves.json').write_text(json.dumps(stat,ensure_ascii=False,indent=2),encoding='utf-8')
fig,axs=plt.subplots(2,1,figsize=(6.0,5.2),sharex=True)
for field,label,color,mark,style in [('structure','结构感知搜索',BLUE,'o','-'),('candidate','多候选精修',ORANGE,'s','--')]:
 axs[0].plot(range(1,6),[x[field+'_mean'] for x in stat],marker=mark,color=color,ls=style,label=label)
 axs[1].plot(range(1,6),[x[field+'_cycles']/1e6 for x in stat],marker=mark,color=color,ls=style)
axs[0].set_ylabel('逐图平均加速比');axs[1].set_ylabel('总周期（百万）');axs[1].set_xlabel('核心数');axs[1].set_xticks(range(1,6));axs[0].legend(frameon=False,ncol=2,loc='upper left',bbox_to_anchor=(0,1.24),fontsize=11)
for i,ax in enumerate(axs):ax.grid(axis='y',alpha=.18);ax.text(.015,.88 if i==0 else .12,'(a)' if i==0 else '(b)',transform=ax.transAxes);ax.margins(x=.06)
fig.tight_layout(h_pad=.7);save(fig,'fig_q1_complete_curves','平均加速比提升不等同于总周期在每种核数上均下降。','q1_curves.json；两方法各500行原始CSV','比较完整核数曲线和不同聚合口径')
aa={r['case']:r for r in a if int(r['cores'])==5};bb={r['case']:r for r in b if int(r['cores'])==5};delta=[dict(case=c,improvement=100*(int(aa[c]['makespan'])-int(bb[c]['makespan']))/int(aa[c]['makespan'])) for c in aa];delta.sort(key=lambda x:(x['improvement'],x['case']))
assert [sum(x['improvement']>0 for x in delta),sum(x['improvement']==0 for x in delta),sum(x['improvement']<0 for x in delta)]==[66,21,13]
(O/'q1_paired.json').write_text(json.dumps(delta,indent=2),encoding='utf-8')
fig,ax=plt.subplots(figsize=(6,3.1));ys=[x['improvement'] for x in delta];ax.bar(range(1,101),ys,color=[BLUE if y>0 else ORANGE if y<0 else GRAY for y in ys],width=.85);ax.axhline(0,color=GRAY,lw=.8);ax.set(xlabel='按改善率排序的算例序号',ylabel='完成周期改善率（%）',xlim=(0,101));ax.grid(axis='y',alpha=.18);ax.text(.02,.95,'66 胜   21 平   13 负',transform=ax.transAxes,va='top');fig.tight_layout();save(fig,'fig_q1_case_gains','五核均值改善伴随13个退步算例。','q1_paired.json；两方法五核逐图周期','识别结果分布与非支配边界')
# 5: merged actual intervals per core and operation family; no invented task start times.
q=json.loads((O/'q2_trace.json').read_text())
def merge(intervals):
 out=[]
 for s,e in sorted(intervals):
  if out and s<=out[-1][1]:out[-1][1]=max(out[-1][1],e)
  else:out.append([s,e])
 return [(s/1000,(e-s)/1000) for s,e in out]
fig,axs=plt.subplots(2,1,figsize=(6.1,5.0),sharex=True)
for j,(key,label) in enumerate([('baseline','(a) 输入初解'),('final','(b) 最终方案')]):
 ax=axs[j];res=q[key]
 for core in res['per_core_timeline']:
  cid=core['core_id'];ops=core['ops']
  for iscopy,c,dy in [(False,BLUE,.08),(True,ORANGE,-.3)]:
   intervals=[(x['start'],x['end']) for x in ops if (x['op'] in ['COPY_IN','COPY_OUT'])==iscopy]
   ax.broken_barh(merge(intervals),(cid+dy,.27),facecolors=c,edgecolors='none')
 ax.axvline(res['makespan']/1000,color=GRAY,ls='--',lw=.8);ax.text(.02,1.06,f"{label}，{res['makespan']:,} 周期",transform=ax.transAxes)
 ax.set_yticks(range(5),[f'核 {i}' for i in range(5)]);ax.set_ylim(-.55,4.6);ax.set_xlim(0,14.4);ax.grid(axis='x',alpha=.15);ax.invert_yaxis()
axs[0].legend(handles=[Patch(color=BLUE,label='计算'),Patch(color=ORANGE,label='搬运')],frameon=False,ncol=2,loc='upper right',bbox_to_anchor=(1,1.24),fontsize=10.5);axs[1].set_xlabel('时间（千周期）');fig.tight_layout(h_pad=1.1)
save(fig,'fig_q2_gantt','case012五核同场景B评价从13406周期降至11971周期。','q2_trace.json；sources.json记录初解及最终官方评价哈希','对比计算、搬运活动与最终完成时刻')
# 6: exact event sequence with explicit times; equal columns denote order only.
q=json.loads((O/'q3_events.json').read_text());d=Diagram(3.1)
labels=['填充','命中','淘汰','未命中','重新填充'];times=[39485,51610,63967,77594,77801];xs=[1,21,41,61,81]
for i,(x,label,t) in enumerate(zip(xs,labels,times)):
 d.box(x,48,18,23,label,LIGHT if i in [2,3] else PALE);d.text(x+9,37,f'{t:,}',fontsize=11)
 if i<4:d.arrow(x+18,59,x+20,59)
d.text(50,89,'case039 · 五核 · 张量 1000000005（4 KiB）',fontsize=11.5)
d.text(10,22,'进入 FIFO',fontsize=10.5);d.text(30,22,'走 L2',fontsize=10.5);d.text(50,22,'新数据挤出',fontsize=10.5);d.text(70,22,'走 DDR',fontsize=10.5);d.text(90,22,'队尾插入',fontsize=10.5)
d.text(50,4,'标注为真实周期；节点间距仅表示事件顺序',fontsize=10.5)
d.drawio('fig_q3_fifo_events');save(d.fig,'fig_q3_fifo_events','FIFO命中不刷新队列位置，曾命中的张量仍可能被淘汰并再次走DDR。','q3_events.json；case039最终方案官方cache_events','追踪真实张量驻留、命中、淘汰与再读取')
(O/'figure_manifest.json').write_text(json.dumps({'version':1,'figures':meta},ensure_ascii=False,indent=2),encoding='utf-8')
print('Generated',len(meta),'figures')

