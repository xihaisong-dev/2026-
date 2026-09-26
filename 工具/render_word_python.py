from pathlib import Path
import sys,os,json
R=Path(__file__).resolve().parents[1];T=R/'tmp/word-two-methods';deps=T/'pydeps'
for x in [deps,deps/'win32',deps/'win32/lib',deps/'Pythonwin'] :sys.path.insert(0,str(x))
os.add_dll_directory(str(deps/'pywin32_system32'))
import pythoncom
from win32com.client import dynamic
pythoncom.CoInitialize()
w=dynamic.Dispatch(pythoncom.CoCreateInstance('Word.Application',None,pythoncom.CLSCTX_LOCAL_SERVER,pythoncom.IID_IDispatch))
d=None
try:
 w.Visible=False;w.DisplayAlerts=0
 d=w.Documents.Open(str(R/'output/论文修订/通用神经网络处理器多核调度论文_两方案修订版.docx'),False,False)
 for sid in [-20,-21]:
  style=d.Styles(sid);style.Font.Size=10.5;style.ParagraphFormat.LineSpacingRule=4;style.ParagraphFormat.LineSpacing=15;style.ParagraphFormat.SpaceAfter=0;style.ParagraphFormat.SpaceBefore=0
 d.Fields.Update();d.Repaginate()
 for i in range(1,d.TablesOfContents.Count+1):d.TablesOfContents(i).Update()
 d.Repaginate()
 for i in range(1,d.TablesOfContents.Count+1):d.TablesOfContents(i).UpdatePageNumbers()
 d.Save();d.ExportAsFixedFormat(str(T/'preview.pdf'),17)
 print('Pages:',d.ComputeStatistics(2))
except Exception as e:print(repr(e));raise
finally:
 if d is not None:d.Close(0)
 w.Quit();pythoncom.CoUninitialize()
