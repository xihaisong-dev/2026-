# 多核调度相关知网文献

5篇全文均由知网页面PDF下载入口取得，原文件未改写。来源、文件大小、页数和SHA-256见[文献清单](文献清单.json)。

阅读建议基于题录、摘要和目录，不代表已完成全文精读；本目录不改变正式研究阶段或门禁。

| 编号 | 全文 | 作者 | 年份 / 来源 | PDF页数 |
| --- | --- | --- | --- | --- |
| 01 | [基于TVM的卷积优化和计算图划分并行调度方法研究与实现](01_基于TVM的卷积优化和计算图划分并行调度方法研究与实现_王朝闻.pdf) | 王朝闻 | 2022 / 西安科技大学 | 112 |
| 02 | [面向SIMD架构智能处理器的编译优化技术研究](02_面向SIMD架构智能处理器的编译优化技术研究_郑鎏韬.pdf) | 郑鎏韬 | 2025 / 中国科学技术大学 | 129 |
| 03 | [带宽受限型多核加速器架构的软硬件协同优化方法](03_带宽受限型多核加速器架构的软硬件协同优化方法_肖星宇.pdf) | 肖星宇、程虎、杨赟辉、魏敬和、张学永 | 2026 / 计算机工程与应用 | 18 |
| 04 | [面向X86多核处理器的数据流程序任务调度与缓存优化](04_面向X86多核处理器的数据流程序任务调度与缓存优化_唐九飞.pdf) | 唐九飞、李鹤、于俊清 | 2016 / 中国科学技术大学学报 | 8 |
| 05 | [基于DAG的自校正最长路径多核调度算法](05_基于DAG的自校正最长路径多核调度算法_许兆淳.pdf) | 许兆淳、杨雨、姜海峰 | 2026 / 导弹与航天运载技术(中英文) | 9 |

## 与赛题的联系

### 01 基于TVM的卷积优化和计算图划分并行调度方法研究与实现

问题一、二：分支识别、子图划分、依赖重建和并行调度。重点阅读第4、5章。

[知网来源](https://kns.cnki.net/kcms2/article/abstract?v=VNVtbp4NFXcVu55tE514VohUAVIWpuP0G9pvFN7TUqjmg2lEH5BGbdxQ20SO6Sjivg2xioSAebg6kGOfeAFhcyvyzYTNGrs57jvrIxlxgstxnhbHdZBaKmX67RhppVT7-Nj9Q9ZakisitewdwWrYv2Ue6EeSE6VLaO74D5QCNg5MsD1OUytJcLTfsLtFrTv-)

### 02 面向SIMD架构智能处理器的编译优化技术研究

问题一、二：片上数据驻留、算子融合、存储层次感知调度。重点阅读第3章。

[知网来源](https://kns.cnki.net/kcms2/article/abstract?v=VNVtbp4NFXc8-OX_RZWGVITSCEu9m7Zobk6boymAzrFwzU1wqWT0zuCTg1sBmvgQsR5o3crnS6mLlAZtYJ2Jit1iwt1FYssSFqgdts6sH-A1VlmF_-vI-5CWONpqcEkCB6-rq-HlM-WMz3cp9ArxxElmNrZCpK2vklWmJu0ouNsWX2MmKCwVkzmr7ggxRnge)

### 03 带宽受限型多核加速器架构的软硬件协同优化方法

三问，尤其问题三：共享输入复用、片外带宽瓶颈、数据流和映射联合优化。首发日期2026-05-19；不得将论文硬件改造能力加入赛题。

[知网来源](https://kns.cnki.net/kcms2/article/abstract?v=VNVtbp4NFXfE67t1aRjpHVxGs-d-caNAG6On0N_wH8nKfCrCMvazDdQmXKqVuSyf6yRdi86wud2RVw6aTw8WMVbCT7k0ptkahPKyNPdoi4jucfE5CFRWqCvEoaXH9BZxztX87JzhHf75w-UvMUEM8ltRHFAZI6lVCwOIvj9W3WTeh-RrDKp2WQ==)

### 04 面向X86多核处理器的数据流程序任务调度与缓存优化

问题一、二：融合、任务粒度、流水并行、通信感知核心映射。46(3):200-207；X86伪共享机制不能直接移植到本题。

[知网来源](https://kns.cnki.net/kcms2/article/abstract?v=VNVtbp4NFXcu9cWgbDIKpGVxizvcGJtuIipJ6zEclrVNKFRs6-oMs1SPSW4n-k2K9gApes_zQG4iRwEz565zMHRlPfNEX1wi_vLymt6UXScIBvjjWVH84oLHvcAum1l0VfYfxNSRPb-RmhjCmyoFlZOheYMZ_MiBR1u7ijKjL27_B8LQ6k5fGg==)

### 05 基于DAG的自校正最长路径多核调度算法

问题一、二：最长路径优先级、多核分配和可行性验证。2026(3):58-66；题目计算周期已知，动态自校正不是主要需求。

[知网来源](https://kns.cnki.net/kcms2/article/abstract?v=VNVtbp4NFXcRpIdJTO9mcdnU-jkF2WE0dQpiJGuKGk5xPuvH-JIqcXGNGT91bgkkS7e7w_0tHOupp4N05qtMKGRgYgrkaA5Hv3ClfKdzEGR_9pEpMfb6YWlRXV1BV1PkLvYkuXXaxlMpSgdURq9tHGNqUHYUl4HKOC5Aho3h3QBRv8vtfjW1tg==)

## 验证边界

已检查PDF文件头、全部页面及内容流解析，并核对文章首页/学位论文封面。下载原件存在部分重复MediaBox键的解析告警，解析可完成，保留原件；未进行全文逐页版式验收或技术结论复核。

建议阅读顺序：01 → 02 → 04 → 03 → 05。
