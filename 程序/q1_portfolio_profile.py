"""Historical candidate audit and case-grouped offline portfolio validation.

No new score or formal solution is produced. The hindsight envelope is diagnostic.
"""
import argparse,csv,gzip,json,hashlib
from collections import Counter,defaultdict
from pathlib import Path
from statistics import mean,median
from q1_io import ROOT,PROCESSED,verify,official,write_json,sha
from q1_solver import Graph

SOURCES={'current':'20260924-A-q1-event-ranking-full100','previous':'20260924-A-q1-ranking-full100'}

def load(p): return json.loads(p.read_text(encoding='utf-8-sig'))
def dump_csv(p,rows):
    with p.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)

def profile(raw,settings,waits):
    g=Graph(raw,settings,waits);seen=set();sizes=[]
    for u in g.order:
        if u in seen:continue
        stack=[u];seen.add(u);n=0
        while stack:
            v=stack.pop();n+=1
            for w in g.pred[v]|g.succ[v]:
                if w not in seen:seen.add(w);stack.append(w)
        sizes.append(n)
    loads=Counter()
    for o in g.ops.values():loads[o['pipe']]+=o['cycles']
    work=sum(loads.values())
    inputs=[t for t in g.tensors if not t[2]]
    return dict(ops=len(g.ops),components=len(sizes),largest_component_fraction=max(sizes)/len(g.ops),
        critical_fraction=max(g.rank.values())/max(1,work),
        dominant_pipe_fraction=max(loads.values())/max(1,work),
        shared_input_fraction=sum(t[0] for t in inputs if len(t[3])>1)/max(1,sum(t[0] for t in inputs)),
        tensor_bytes_per_cycle=sum(t[0] for t in g.tensors)/max(1,work),
        fanout_max=max(map(len,g.succ.values()),default=0))

def stats(rows,field):
    out=[]
    for k in range(2,6):
        rr=[r for r in rows if r['cores']==k]
        total=sum(r[field] for r in rr);base=sum(r['current'] for r in rr)
        out.append(dict(cores=k,total_cycles=total,mean_speedup=mean(r['single']/r[field] for r in rr),
            reduction_pct=100*(base-total)/base,wins=sum(r[field]<r['current'] for r in rr),
            ties=sum(r[field]==r['current'] for r in rr),losses=sum(r[field]>r['current'] for r in rr)))
    return out

def loss(rows,action):return sum(r[action]/r['current'] for r in rows)
def best_action(rows):return min(['current','previous'],key=lambda a:(loss(rows,a),a!='current'))
FEATURES=['ops','components','largest_component_fraction','critical_fraction','dominant_pipe_fraction','shared_input_fraction','tensor_bytes_per_cycle','fanout_max','cores']
def fit_stump(train):
    action=best_action(train);best=loss(train,action);model=dict(action=action)
    # Fixed shallow model; no test-fold values or case identifier enter split fitting.
    for f in FEATURES:
        vals=sorted(set(r[f] for r in train))
        thresholds=sorted(set(vals[min(len(vals)-1,int((len(vals)-1)*q))] for q in [.25,.5,.75]))
        for threshold in thresholds:
            left=[r for r in train if r[f]<=threshold];right=[r for r in train if r[f]>threshold]
            if min(len({r['case'] for r in x}) for x in [left,right])<10:continue
            a,b=best_action(left),best_action(right)
            score=loss(left,a)+loss(right,b)
            if score<best-1e-10:best=score;model=dict(feature=f,threshold=threshold,left=a,right=b)
    return model
def choose(model,row):return model['action'] if 'action' in model else model['left'] if row[model['feature']]<=model['threshold'] else model['right']

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    assert not a.output.exists();manifest=verify();mod=official()
    from evaluation_validation import read_evaluation_config
    cfg=PROCESSED/'data/config.txt';settings=read_evaluation_config(str(cfg));waits=mod.read_scene_a_config(str(cfg))
    summaries={tag:load(ROOT/'图表/runs'/name/'summary.json') for tag,name in SOURCES.items()}
    assert len({s['source_zip_sha256'] for s in summaries.values()})==1
    assert len({s['config_sha256'] for s in summaries.values()})==1
    data={};candidates=[];audits=[];family=defaultdict(list)
    for tag,name in SOURCES.items():
        root=ROOT/'图表/runs'/name;summary=summaries[tag];assert len(summary['runs'])==400
        for run in summary['runs']:
            key=(run['case'],int(run['cores']));folder=root/f"{key[0]}_{key[1]}cores_seed0_{run['config']}"
            search=load(folder/'search.json');ev=search['evaluations']
            with gzip.open(folder/'evaluation.json.gz','rt',encoding='utf-8') as f:final=json.load(f)
            assert final['makespan']==run['makespan']==min(e['makespan'] for e in ev)
            assert run['evaluated_opportunities']==12 and run['seed']==0
            assert summary['input_sha256'][key[0]+'.json']==sha((PROCESSED/'data'/f'{key[0]}.json').read_bytes())
            row=data.setdefault(key,dict(case=key[0],cores=key[1],single=run['single_makespan']))
            assert row['single']==run['single_makespan']
            row[tag]=run['makespan'];row[tag+'_seconds']=run['solve_seconds'];row[tag+'_winner']=run['best_candidate']
            ledger={x['evaluation_id']:x.get('plan_sha256','') for x in search.get('proposal_ledger',[]) if x.get('evaluation_id') is not None}
            for i,e in enumerate(ev):
                candidate=dict(case=key[0],cores=key[1],version=tag,position=i,candidate=e['candidate'],
                    makespan=e['makespan'],added_copy_bytes=e['added_copy_bytes'],seconds=e.get('evaluation_seconds'),
                    cache_hit=e.get('cache_hit',False),plan_sha256=ledger.get(i,''),
                    improvement_over_prefix=0 if i==0 else max(0,min(x['makespan'] for x in ev[:i])-e['makespan']))
                candidates.append(candidate);family[(tag,e['candidate'])].append(candidate)
        audits.append(dict(version=tag,configurations=400,final_matches_log_minimum=True,final_matches_saved_evaluator=True,
            summary_sha256=sha((root/'summary.json').read_bytes()),budget=12))
    profiles={}
    for case in sorted({k[0] for k in data}):
        raw=load(PROCESSED/'data'/f'{case}.json');profiles[case]=profile(raw,settings,waits)
    rows=[]
    for key,r in sorted(data.items()):
        assert 'current' in r and 'previous' in r
        r.update(profiles[r['case']]);r['oracle']=min(r['current'],r['previous'])
        r['oracle_gain']=r['current']-r['oracle'];r['oracle_pool_seconds']=r['current_seconds']+r['previous_seconds']
        r['fold']=int(hashlib.sha256(r['case'].encode()).hexdigest()[:8],16)%5
        rows.append(r)
    folds=[]
    for fold in range(5):
        train=[r for r in rows if r['fold']!=fold];test=[r for r in rows if r['fold']==fold]
        model=fit_stump(train);folds.append(dict(fold=fold,train_cases=len({r['case'] for r in train}),test_cases=len({r['case'] for r in test}),model=model))
        for r in test:
            r['chosen']=choose(model,r);r['offline_cv']=r[r['chosen']];r['offline_seconds']=r[r['chosen']+'_seconds']
    a.output.mkdir(parents=True)
    dump_csv(a.output/'configuration_profile.csv',rows);dump_csv(a.output/'candidate_ledger.csv',candidates)
    dump_csv(a.output/'graph_profile.csv',[dict(case=k,**v) for k,v in sorted(profiles.items())])
    fr=[dict(version=k[0],candidate=k[1],count=len(v),improving_calls=sum(x['improvement_over_prefix']>0 for x in v),
        saved_cycles=sum(x['improvement_over_prefix'] for x in v),evaluation_seconds=sum(x['seconds'] or 0 for x in v)) for k,v in sorted(family.items())]
    dump_csv(a.output/'candidate_contribution.csv',fr)
    report=dict(scope='Q1 historical offline diagnosis; not a new formal 100-case result',audits=audits,
        current=stats(rows,'current'),hindsight=stats(rows,'oracle'),offline_grouped_cv=stats(rows,'offline_cv'),folds=folds,
        current_search_seconds=sum(r['current_seconds'] for r in rows),oracle_two_runs_seconds=sum(r['oracle_pool_seconds'] for r in rows),
        offline_selected_seconds=sum(r['offline_seconds'] for r in rows),
        timing_limit='Historical mixed-host search times, excluding cold baselines and final verification; not a controlled wall-clock benchmark',
        known_development_leakage='Both historical algorithms were developed using this corpus; grouped CV prevents selector label leakage across cores, but is not external validation',
        within_run_oracle_gain=0,candidate_rows=len(candidates),top_losses=sorted(rows,key=lambda r:-r['oracle_gain'])[:20])
    write_json(a.output/'report.json',report)
    lines=['# 问题一结构—算法收益—耗时画像','', '仅使用两个覆盖全部100图、2—5核、每配置12机会的冻结历史版本；不是新增正式成绩。', '',
           '## 周期与加速比', '', '|核数|当前平均加速比|跨版本事后择优|分组交叉验证选择|事后最多节省周期|', '|---|---:|---:|---:|---:|']
    for x,y,z in zip(report['current'],report['hindsight'],report['offline_grouped_cv']):
        lines.append(f"|{x['cores']}|{x['mean_speedup']:.6f}|{y['mean_speedup']:.6f}|{z['mean_speedup']:.6f}|{x['total_cycles']-y['total_cycles']}|")
    lines+=['','## 解释与限制','',
        '800份日志的返回方案均等于各自已评价候选的最短周期，单次候选池内部事后择优的新增收益为零。跨版本择优是已观察候选并集的诊断包络，不是全局最优界，也不能算作12次预算成绩。',
        '交叉验证按case分为5折，同一图所有核数都在同一折。每折仅用训练图拟合深度1决策树，特征阈值限定四分位点、每叶至少10张图，目标为相对当前方案的平均归一化周期；测试图只选择一个已记录的完整12机会算法。没有混合两个版本中依赖不同搜索状态的候选前缀。',
        '这只是历史结果上的离线选择器验证；两个算法本身已在这100图上开发，因此不能宣称未见图泛化。历史耗时来自不同机器且只计搜索，不可证明端到端加速。候选级用时含缓存命中，候选的边际贡献依赖当时前缀，不能解释成独立因果效应。',
        '下一步必须先冻结选择规则及算法快照，再统一环境重跑；若离线选择退步，不应替换现行默认方案。新增候选生成能力仍需另做同预算实验。','', '## 事后互补最大的配置','']
    for r in report['top_losses'][:10]:
        if r['oracle_gain']>0:lines.append(f"- {r['case']} / {r['cores']}核：可少{r['oracle_gain']}周期；当前{r['current_winner']}，旧版{r['previous_winner']}；最大分量占比{r['largest_component_fraction']:.3f}。")
    (a.output/'report.md').write_bytes(('\n'.join(lines)+'\n').encode())
    print(json.dumps({k:report[k] for k in ['candidate_rows','current','hindsight','offline_grouped_cv']},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
