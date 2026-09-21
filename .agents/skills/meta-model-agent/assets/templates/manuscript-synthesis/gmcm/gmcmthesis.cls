% Local 2026 adaptation. Official artwork remains in assets/.
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{gmcmthesis}[2026/09/21 Huawei GMCM official-format adaptation]
\DeclareOption{withoutpreface}{}
\DeclareOption{bwprint}{}
\DeclareOption*{\PassOptionsToClass{\CurrentOption}{article}}
\ProcessOptions\relax
\LoadClass[a4paper,12pt]{article}
\RequirePackage{iftex}
\RequireXeTeX
\RequirePackage[UTF8,fontset=windows,scheme=plain,heading=true,linespread=1]{ctex}
\RequirePackage{geometry}
\geometry{top=30mm,bottom=18mm,left=22.5mm,right=22.5mm,footskip=10mm}
\setmainfont{Times New Roman}
\setsansfont{Arial}
\setmonofont{Consolas}
\providecommand{\song}{\songti}
\providecommand{\kai}{\kaishu}
\renewcommand{\baselinestretch}{1}
\renewcommand\normalsize{\@setfontsize\normalsize{12bp}{14.4bp}%
  \abovedisplayskip=8pt plus 2pt minus 2pt
  \belowdisplayskip=8pt plus 2pt minus 2pt
  \abovedisplayshortskip=4pt plus 2pt
  \belowdisplayshortskip=4pt plus 2pt}
\normalsize
\setlength{\parindent}{2em}
\setlength{\parskip}{0pt}
\ctexset{section={format=\centering\heiti\zihao{4},beforeskip=1.2ex plus .2ex,afterskip=1ex},
  subsection={format=\songti\zihao{-4},beforeskip=1ex,afterskip=.6ex},
  subsubsection={format=\songti\zihao{-4},beforeskip=.8ex,afterskip=.5ex}}
\setcounter{secnumdepth}{3}
\setcounter{tocdepth}{3}
\RequirePackage{amsmath,amssymb,amsthm,bm}
\RequirePackage{graphicx,xcolor,array,booktabs,longtable,tabularx,multirow}
\RequirePackage{caption,subcaption,listings,enumitem,appendix}
\RequirePackage{pdfpages,tikz,placeins,needspace}
\RequirePackage[hidelinks,unicode,pdfauthor={},pdftitle={}]{hyperref}
\RequirePackage[nameinlink,noabbrev]{cleveref}
\captionsetup{font=normalsize,labelsep=quad,skip=6pt}
\renewcommand{\refname}{参考文献}
\renewcommand{\contentsname}{目录}
\renewcommand{\figurename}{图}
\renewcommand{\tablename}{表}
\AtBeginDocument{\renewcommand{\lstlistingname}{程序}}
\crefname{equation}{式}{式}
\crefname{figure}{图}{图}
\crefname{table}{表}{表}
\newtheorem{theorem}{定理}
\newtheorem{lemma}{引理}
\newtheorem{definition}{定义}
\newtheorem{proposition}{命题}
\renewcommand{\proofname}{证明}
\lstset{language=Python,basicstyle=\small\ttfamily,breaklines=true,
  columns=fullflexible,keepspaces=true,frame=single,numbers=left,
  numberstyle=\scriptsize,xleftmargin=2em,framexleftmargin=1.5em,
  showstringspaces=false,tabsize=4}
\setlist{nosep}
\pagestyle{plain}
\raggedbottom
\endinput
