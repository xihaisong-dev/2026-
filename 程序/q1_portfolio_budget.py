"""Summarize order-dependent budget contributions from the audited candidate CSV."""
import argparse,csv
from collections import defaultdict
from statistics import median
from q1_io import write_json
from q1_portfolio_profile import dump_csv
from pathlib import Path

def main():
    ap=argparse.ArgumentParser();ap.add_argument('directory',type=Path);args=ap.parse_args();root=args.directory
    with (root/'candidate_ledger.csv').open(encoding='utf-8') as f: candidates=list(csv.DictReader(f))
    with (root/'configuration_profile.csv').open(encoding='utf-8') as f: profiles=list(csv.DictReader(f))
    grouped=defaultdict(list)
    for c in candidates:
        if c['version']=='current':grouped[c['case'],int(c['cores'])].append(c)
    rows=[];families=defaultdict(list)
    for p in profiles:
        ev=sorted(grouped[p['case'],int(p['cores'])],key=lambda r:int(r['position']))
        assert len(ev)==12
        prefix=min(int(e['makespan']) for e in ev[:8]);final=int(p['current'])
        bucket='distributed_components' if float(p['largest_component_fraction'])<=.5 else 'dominant_component'
        rows.append(dict(case=p['case'],cores=int(p['cores']),structure=bucket,prefix8=prefix,final12=final,
            late_gain=prefix-final,search_seconds=float(p['current_seconds']),
            late_evaluation_seconds=sum(float(e['seconds']) for e in ev[8:] if e['seconds'])))
        for e in ev:
            name=e['candidate'];family='region_repair' if name.startswith('region_') else 'structural_seed' if name.startswith('structural_') else name
            families[family].append(e)
    contribution=[]
    for name,v in sorted(families.items()):
        contribution.append(dict(family=name,calls=len(v),direct_improving_calls=sum(int(x['improvement_over_prefix'])>0 for x in v),
            direct_saved_cycles=sum(int(x['improvement_over_prefix']) for x in v),evaluation_seconds=sum(float(x['seconds']) for x in v if x['seconds'])))
    buckets=[]
    for name in sorted({r['structure'] for r in rows}):
        v=[r for r in rows if r['structure']==name]
        buckets.append(dict(structure=name,configurations=len(v),late_improving_configurations=sum(r['late_gain']>0 for r in v),
            late_saved_cycles=sum(r['late_gain'] for r in v),median_search_seconds=median(r['search_seconds'] for r in v),
            late_evaluation_seconds=sum(r['late_evaluation_seconds'] for r in v)))
    dump_csv(root/'budget_by_configuration.csv',rows);dump_csv(root/'budget_by_family.csv',contribution)
    write_json(root/'budget_profile.json',dict(structures=buckets,zero_direct_gain=[r for r in contribution if not r['direct_improving_calls'] and r['family']!='single_task'],
        caveat='Prefix/direct gains are order-dependent, not causal removal tests. Non-winning candidates may affect subsequent proposal state.'))
    lines=['','## 预算画像（现行算法，顺序条件下的直接贡献）','',
        '|结构|配置数|后4次有改善的配置|后4次合计节省周期|搜索秒数中位数|','|---|---:|---:|---:|---:|']
    for r in buckets:lines.append(f"|{r['structure']}|{r['configurations']}|{r['late_improving_configurations']}|{r['late_saved_cycles']}|{r['median_search_seconds']:.3f}|")
    lines+=['','以下族在历史顺序下没有直接刷新最优周期，应优先检查机会成本；不能据此直接删除，因为未胜出的候选也可能影响后续提案。']
    for r in contribution:
        if not r['direct_improving_calls'] and r['calls']>=10 and r['family']!='single_task':lines.append(f"- {r['family']}：{r['calls']}次，记录的评价耗时合计{r['evaluation_seconds']:.1f}秒（混合主机、含缓存，不代表单机实测加速）。")
    lines.append('整图单核保底是第一个参考值，其直接改善记为零不代表无效，不纳入上述可疑机会。结构按最大弱连通分量算子数占比是否超过0.5分组，仅作结构分层，不等价于已证明的瓶颈类型。')
    target=root/'report.md';base=target.read_text(encoding='utf-8').split('\n## 预算画像')[0].rstrip()
    target.write_bytes((base+'\n'+'\n'.join(lines)+'\n').encode())
    print(buckets)

if __name__=='__main__':main()
