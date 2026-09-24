"""Report complete matched pairs separately from timeout-censored attempts."""
import argparse
import json
from pathlib import Path
from q1_io import sha, write_json
from q1_ablation_report import collect, compare


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--batches',nargs='+',type=Path,required=True)
    p.add_argument('--regressions',nargs='+',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    report={'batch_comparisons':[], 'regression_comparison':None, 'complete_runs':0,
            'timeout_runs':0,'failed_runs':0,'known_complete_official_calls':0,
            'partial_timeout_official_calls':'unknown; not included in complete counts',
            'source_sha256':{},'prefix_pairs_checked':0}
    lines=['# 第七轮冻结分层验证','','所有候选预算为12；逐运行90秒，缓存关闭。超时不计成绩。','']
    new_keys=set()

    def prefix_check(root, rows):
        keys={(r['case'],r['cores'],r['seed'],r['config']):r for r in rows}
        count=0
        for (case,cores,seed,config),row in keys.items():
            if config!='guarded_joint':continue
            other=keys.get((case,cores,seed,'insertion_rank'))
            if not other:continue
            def history(r):
                name=f"{r['case']}_{r['cores']}cores_seed{r['seed']}_{r['config']}"
                folder=Path(r.get('_folder',root))
                data=json.loads((folder/name/'search.json').read_text(encoding='utf-8'))
                return [(e['candidate'],e['makespan'],e['added_copy_bytes']) for e in data['evaluations'][:9]]
            if history(row)!=history(other):raise ValueError('Protected prefix changed')
            count+=1
        return count

    for folder in args.batches:
        path=folder/'batch.json';state=json.loads(path.read_text(encoding='utf-8'))
        if not state['finished']:raise ValueError('Unfinished batch')
        report['source_sha256'][str(path)]=sha(path.read_bytes())
        done=[]
        lines += [f'## {folder.name}','','| 图/核数 | 基础时间 | 新策略时间 | 状态 |','| --- | ---: | ---: | --- |']
        for row in state['runs']:
            if row['status']=='complete':
                child=folder/row['directory'];verified=collect(child)['runs'][0]
                if verified['makespan']!=row['result']['makespan']:raise ValueError('Batch metric mismatch')
                verified['_folder']=str(child);done.append(verified)
                report['complete_runs']+=1
                report['known_complete_official_calls']+=verified.get('official_calls',verified['evaluations'])
                new_keys.add((row['case'],row['cores']))
            elif row['status']=='timeout':report['timeout_runs']+=1
            else:report['failed_runs']+=1
        paired=[]
        for case,cores,seed in sorted({(r['case'],r['cores'],r['seed']) for r in state['runs']}):
            group=[r for r in state['runs'] if (r['case'],r['cores'],r['seed'])==(case,cores,seed)]
            times={r['config']:r.get('result',{}).get('makespan',r['status']) for r in group}
            ok=all(r['status']=='complete' for r in group)
            if ok:paired.extend(r for r in done if (r['case'],r['cores'],r['seed'])==(case,cores,seed))
            lines.append(f"| {case}/{cores} | {times['insertion_rank']} | {times['guarded_joint']} | {'完成' if ok else '排除：未完整配对'} |")
        comparison=compare(paired,'insertion_rank','guarded_joint') if paired else None
        report['prefix_pairs_checked']+=prefix_check(folder,paired)
        report['batch_comparisons'].append({'batch':str(folder),'comparison':comparison})
        if comparison:
            lines += ['',f"完成配对：胜{comparison['wins']}/平{comparison['ties']}/负{comparison['losses']}；平均时间降幅{comparison['mean_paired_reduction_percent']:.3f}%。",'']
    regressions=[]
    for folder in args.regressions:
        verified=collect(folder)
        report['source_sha256'][str(folder/'summary.json')]=sha((folder/'summary.json').read_bytes())
        for row in verified['runs']:
            row['_folder']=str(folder);regressions.append(row)
            report['complete_runs']+=1
            report['known_complete_official_calls']+=row.get('official_calls',row['evaluations'])
    report['prefix_pairs_checked']+=prefix_check('',regressions)
    report['regression_comparison']=compare(regressions,'insertion_rank','guarded_joint')
    report['new_case_core_complete']=sorted(new_keys)
    lines += ['## 旧退步回归','','| 配置 | 基础 | 新策略 |','| --- | ---: | ---: |']
    for r in report['regression_comparison']['pairs']:
        lines.append(f"| {r['case']}/{r['cores']}/seed{r['seed']} | {r['before']} | {r['after']} |")
    lines += ['',f"完整运行{report['complete_runs']}次，已知完整官方调用{report['known_complete_official_calls']}次；超时{report['timeout_runs']}次，其未完成调用数未知。",
              f"新增完整case×核数配置{len(new_keys)}组；前9次候选一致性已核验{report['prefix_pairs_checked']}个配对。",
              '不把超时纳入平均成绩，幸存样本可能偏向小图；不把下界称为可达最优。新策略保持可选，未默认替换。','']
    args.output.mkdir(parents=True,exist_ok=False)
    write_json(args.output/'analysis.json',report)
    (args.output/'report.md').write_bytes('\n'.join(lines).encode('utf-8'))
    print(json.dumps({k:report[k] for k in ['complete_runs','timeout_runs','known_complete_official_calls','prefix_pairs_checked']},ensure_ascii=True))


if __name__=='__main__':main()
