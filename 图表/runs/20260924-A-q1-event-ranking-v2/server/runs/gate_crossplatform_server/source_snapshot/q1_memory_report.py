"""Check bounded routing trials against frozen full100 rows, no ex-post oracle."""
import argparse, csv, json
from pathlib import Path
from statistics import mean
from q1_io import sha, write_json, verify


def load(p):return json.loads(p.read_text(encoding='utf8'))


def main():
    ap=argparse.ArgumentParser()
    for x in ['runs','baseline','diagnostics','runtime','output']:ap.add_argument('--'+x,type=Path,required=True)
    a=ap.parse_args();a.output.mkdir(parents=True,exist_ok=False);manifest=verify()
    old=load(a.baseline/'summary.json');base={(r['case'],r['cores']):r for r in old['runs']}
    results={};rows=[]
    for name in ['component_memory','component_hybrid']:
        root=a.runs/name;s=load(root/'summary.json')
        assert s['completed'] and not s['failures'] and len(s['runs'])==20
        assert len({(r['case'],r['cores'],r['seed']) for r in s['runs']})==20
        assert s['config_sha256']==old['config_sha256']==manifest['files']['data/config.txt']
        for case,h in s['input_sha256'].items():assert h==old['input_sha256'][case]==manifest['files']['data/'+case]
        for f,h in s['code_sha256'].items():assert sha((root/'source_snapshot'/f).read_bytes())==h
        group=[]
        for r in s['runs']:
            b=base[r['case'],r['cores']];assert r['single_makespan']==b['single_makespan']
            folder=root/f"{r['case']}_{r['cores']}cores_seed0_{name}"
            for f,h in r['artifacts'].items():assert sha((folder/f).read_bytes())==h
            assert all(load(folder/'verification.json').values())
            st=load(folder/'search.json');assert len(st['evaluations'])==12 and st['official_calls']==11
            assert st['protected_grain_attempts']==[.5,1.,2.,.25]
            assert (r['makespan'],r['added_copy_bytes'])==min((x['makespan'],x['added_copy_bytes']) for x in st['evaluations'])
            assert st['structural_seed_stats'].get('local_preparation',{}).get('calls',0)<=3
            assert st['structural_seed_stats'].get('local_preparation',{}).get('global_evaluations',0)==0
            target=r['case'] not in ['case_028','case_067']
            plan_match = load(folder/'plan.json')==load(a.baseline/f"{r['case']}_{r['cores']}cores_seed0_component_local_rank"/'plan.json')
            row=dict(config=name,case=r['case'],cores=r['cores'],target=target,before=b['makespan'],after=r['makespan'],
                     single=r['single_makespan'],before_bytes=b['added_copy_bytes'],after_bytes=r['added_copy_bytes'],
                     after_spill=r['spill_added_copy_bytes'],solve_seconds=r['solve_seconds'],validation_seconds=r['verification_seconds'],
                     structural_evaluations=r['structural_evaluations'],best_candidate=r['best_candidate'],plan_matches_baseline=plan_match)
            group.append(row);rows.append(row)
        target=[r for r in group if r['target']]
        results[name]=dict(wins=sum(r['after']<r['before'] for r in target),ties=sum(r['after']==r['before'] for r in target),losses=sum(r['after']>r['before'] for r in target),
            time_reduction_pct=100*(1-sum(r['after'] for r in target)/sum(r['before'] for r in target)),
            bytes_reduction_pct=100*(1-sum(r['after_bytes'] for r in target)/sum(r['before_bytes'] for r in target)),
            per_core={k:dict(before=mean(r['single']/r['before'] for r in target if r['cores']==k),after=mean(r['single']/r['after'] for r in target if r['cores']==k)) for k in range(2,6)},protection_matches=sum(r['plan_matches_baseline'] for r in group if not r['target']),protection_regressions=[r for r in group if not r['target'] and r['after']>r['before']])
    diag=load(a.diagnostics/'summary.json');assert diag['completed'] and len(diag['rows'])==24
    result=dict(verified=True,scope='six targeted development graphs, two large protection graphs; not full100',variants=results,
                formal_runs=40,score_calls=440,reference_hits=40,final_official_replays=40,diagnostic_score_calls=sum(x['global_calls'] for x in diag['rows']))
    runtime=load(a.runtime/'fast-check/summary.json');paired=load(a.runtime/'paired-check/summary.json')
    assert runtime['completed'] and paired['completed'] and len(runtime['rows'])==4 and len(paired['rows'])==2
    for r in runtime['rows']+paired['rows']:
        assert all(r['checks'].values()) and r['full_score_calls']==11 and r['reference_hits']==1
        prior=a.baseline/f"case_091_{r['cores']}cores_seed0_component_local_rank"
        assert sha((prior/'evaluation.json.gz').read_bytes())==r['archived_official_result_sha256']
    pair={r['fast']:r for r in paired['rows']}
    result['runtime']=dict(four_core_checks=runtime['rows'],paired=paired['rows'],paired_speedup=pair[False]['seconds']/pair[True]['seconds'],paired_time_reduction_pct=100*(1-pair[True]['seconds']/pair[False]['seconds']),scope='single host sequential single-worker pair; background campaign load not constant; reference cold computation and original final replay excluded')
    write_json(a.output/'summary.json',result)
    with (a.output/'comparison.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    lines=['# 内存路由与主导分量试验','',result['scope'],'','| 方案 | 目标12组胜/平/负 | 总时间下降 | 额外搬运下降 |','|---|---:|---:|---:|']
    for n,r in results.items():lines.append(f"| {n} | {r['wins']}/{r['ties']}/{r['losses']} | {r['time_reduction_pct']:.4f}% | {r['bytes_reduction_pct']:.4f}% |")
    lines+=['','每方案另外8组大图保护检查；完整分量内存路由出现1组退步，主导分量路由8组完全一致。每组12机会，四基础粒度保留；原版最终复核40份通过。诊断调用单列，离线最优候选不作为求解成绩。','',
        '并集内存量不是峰值，但真实溢出也不等于总体性能差；是否接受候选仍由官方Makespan主目标决定。主导分量仅拓扑连续有界切分，不穷举切点。','',
        '当前是定向开发验证，不能声称新的100图成绩。运行时间为并发服务器墙钟，原版复核单列，未承诺所有用例10分钟内完成。','',
        '| case | 核数 | 方案 | 原时间 | 新时间 | 新溢出bytes |','|---|---:|---|---:|---:|---:|']
    for r in sorted(rows,key=lambda r:(r['case'],r['cores'],r['config'])):
        if r['target']:lines.append(f"| {r['case']} | {r['cores']} | {r['config']} | {r['before']} | {r['after']} | {r['after_spill']} |")
    for name,data in results.items():
        for r in data['protection_regressions']:
            lines.append(f"保护组退步：{name} / {r['case']} / {r['cores']}核，{r['before']} → {r['after']}，增加{100*(r['after']/r['before']-1):.6f}%。不得声称全保护通过，也不直接替换默认。")
    lines += ['', 'case_028四核的轨迹检查：新增 structural_memory_lpt 的官方时间13608312，高于当时最优11035873；它未更新成本观测，但消耗一个预算位置。原基线后续local_reschedule将10694242改善为10676362，新流程在相同12机会下没有执行这一有效重排。因此本例退步来自预算机会成本，不能把普通扰动名义位置理解为免费机会。']
    lines+=['','## case_091 求解时间', '', '| 核数 | 快速搜索秒数 | 完整轨迹/方案/评价一致 |','|---|---:|---|']
    for r in runtime['rows']:lines.append(f"| {r['cores']} | {r['seconds']:.3f} | 是 |")
    lines += ['',f"另一次同机单worker顺序对照：五核旧版{pair[False]['seconds']:.3f}秒，新版{pair[True]['seconds']:.3f}秒；本次观测{result['runtime']['paired_speedup']:.3f}倍、耗时减少{result['runtime']['paired_time_reduction_pct']:.3f}%。只有一次配对，后台负载有变化，不是统计置信结论。",'改动仅用子图DAG的可达性判断合并是否成环，按已接受合并增量更新；不减少搜索预算。四核数及额外配对的最终输出完全等同既有官方已验证方案，故复用原版核验证据；本轮没有重复这六次昂贵原版最终复核。', '四核数搜索均低于5分钟不等于端到端全部低于10分钟：固定单核冷计算和原版最终复核需另计。原cProfile诊断在收集749个采样后中断，保留中断日志；没有把剖析耗时当作性能基准。']
    (a.output/'report.md').write_bytes(('\n'.join(lines)+'\n').encode());print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
