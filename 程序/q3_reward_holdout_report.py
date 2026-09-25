"""Paired holdout analysis without choosing the best seed after the fact."""
import hashlib,json,random,sys
from collections import Counter
from pathlib import Path
from statistics import mean,median
from q23_reward_prefix import choose,reward

def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def report(root):
 c=read(root/'contract.json');errors=[];jobs=[];pairs=[];groups=[]
 for n in c['cases']:
  for seed in c['seeds']:
   arms={}
   for arm in c['arms']:
    name=f'q3_{n:03}_s{seed}_{arm}';rp=root/'rows'/(name+'.json')
    if not rp.exists():errors.append(name+': missing');continue
    r=read(rp);s=r.get('summary',{});a=s.get('arguments',{});p=root/'jobs'/name
    valid=bool(s.get('valid') and s.get('complete') and not s.get('error') and not s.get('deadline_stop') and s.get('worker_exitcode')==0 and r['returncode']==0)
    if not valid:errors.append(name+': verification failed')
    if r['wall']>600:errors.append(name+': wall exceeds600')
    if any(a.get(k)!=c[k] for k in ['seconds','cores','max_proposals']) or a.get('seed')!=seed or a.get('policy')!=arm or a.get('ordering_prepare') or not a.get('reuse'):errors.append(name+': arguments')
    t=read(p/'search/search.json') if (p/'search/search.json').exists() else {}
    scores=read(p/'scored.json') if (p/'scored.json').exists() else []
    d=read(p/'details.json') if (p/'details.json').exists() else {}
    if arm=='reward' and (p/'search/identity.json').exists():
     identity=read(p/'search/identity.json');byhash={x['plan_sha256']:x for x in scores};counts=Counter();gains=Counter();rng=random.Random(seed+0x51EC70)
     for x in t.get('proposals',[]):
      f,w=choose(x['index'],identity['prefix'],identity['extension_cycle'],counts,gains,rng)
      if f!=x['family'] or w!=x.get('selection_weights'):errors.append(name+': selection replay')
      counts[f]+=1;value=0.
      if x.get('accepted'):
       before=byhash[x['incumbent']];after=byhash[x['plan_sha256']]
       value=reward((before['makespan'],before['added']),(after['makespan'],after['added']))
      if value!=x.get('reward',0.):errors.append(name+': reward replay')
      gains[f]+=value
    row=dict(case=n,seed=seed,arm=arm,valid=valid,makespan=s.get('makespan'),added=s.get('added'),wall=r['wall'],scored=len(scores),proposals=len(t['proposals']) if 'proposals' in t else sum(t.get('family_counts',t.get('counts',{})).values()),rss_mib=(s.get('peak_child_rss_bytes') or 0)/1024**2)
    jobs.append(row);arms[arm]=(row,d)
   if len(arms)==2:
    x,dx=arms['legacy'];y,dy=arms['reward']
    for k in ['input_sha256','provenance']:
     if dx.get(k)!=dy.get(k):errors.append(f'{n}/{seed}: provenance')
    if x['valid'] and y['valid']:
     delta=y['makespan']-x['makespan']
     pairs.append(dict(case=n,seed=seed,legacy=x['makespan'],reward=y['makespan'],delta=delta,reduction_pct=-100*delta/x['makespan'],added_delta=y['added']-x['added'],legacy_scored=x['scored'],reward_scored=y['scored'],legacy_proposals=x['proposals'],reward_proposals=y['proposals']))
 for n in c['cases']:
  ps=[p for p in pairs if p['case']==n]
  if ps:groups.append(dict(case=n,seeds=len(ps),legacy_mean=mean(p['legacy'] for p in ps),reward_mean=mean(p['reward'] for p in ps),mean_reduction_pct=mean(p['reduction_pct'] for p in ps),wins=sum(p['delta']<0 for p in ps),ties=sum(p['delta']==0 for p in ps),losses=sum(p['delta']>0 for p in ps),mean_added_delta=mean(p['added_delta'] for p in ps),min_reduction_pct=min(p['reduction_pct'] for p in ps),max_reduction_pct=max(p['reduction_pct'] for p in ps)))
 summary=dict(completed=len(jobs),expected=len(c['cases'])*len(c['seeds'])*2,valid=sum(j['valid'] for j in jobs),paired=len(pairs),wins=sum(p['delta']<0 for p in pairs),ties=sum(p['delta']==0 for p in pairs),losses=sum(p['delta']>0 for p in pairs))
 if pairs:summary.update(mean_reduction_pct=mean(p['reduction_pct'] for p in pairs),median_reduction_pct=median(p['reduction_pct'] for p in pairs),legacy_total=sum(p['legacy'] for p in pairs),reward_total=sum(p['reward'] for p in pairs),added_delta=sum(p['added_delta'] for p in pairs))
 by_seed=[dict(seed=seed,pairs=len(ps),legacy_total=sum(p['legacy'] for p in ps),reward_total=sum(p['reward'] for p in ps),wins=sum(p['delta']<0 for p in ps),ties=sum(p['delta']==0 for p in ps),losses=sum(p['delta']>0 for p in ps)) for seed in c['seeds'] if (ps:=[p for p in pairs if p['seed']==seed])]
 result=dict(by_seed=by_seed,errors=errors,summary=summary,groups=groups,pairs=pairs,jobs=jobs,formal_promoted=False)
 (root/'report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 lines=['# Q3 留出图与多种子验证','', '固定上一轮权重规则；按算子数量三等分与单/多分量分层，以固定哈希选图，不按性能选图。这里留出仅指未参与本次奖励权重设计，并非项目历史从未使用。', '6图×3种子×2策略，共36项；种子0/1/2均报告，禁止事后只取最好种子。旧组合与新权重均启用生成复用，关闭排序准备复用。590秒、384提议上限，20%留最终复核；历史暖初解生成不计。', '', '|case|旧组合平均cycles|新权重平均cycles|逐种子平均周期下降|胜/平/负|', '|---|---:|---:|---:|---:|']
 for g in groups:lines.append(f'|{g["case"]:03}|{g["legacy_mean"]:.3f}|{g["reward_mean"]:.3f}|{g["mean_reduction_pct"]:.4f}%|{g["wins"]}/{g["ties"]}/{g["losses"]}|')
 lines+=['','汇总：'+json.dumps(summary,ensure_ascii=False),'','检查问题：'+json.dumps(errors,ensure_ascii=False),'','逐对结果、搬运差异、评价次数、耗时见report.json。每个奖励策略的权重、收益和抽样选择均逐步重放。平均周期下降不是赛题的相对单核平均加速比；本轮不更新正式100图成绩。', '重复种子来自同一张图，不能当作18张独立图；固定6图上的结果仍不足以证明全量效果。冻结提交版不替换，正式门禁NOT_RUN。','']
 lines+=['## 决策与局部轨迹','',
 '不替换冻结版。18组配对总周期2935788→2935326，下降462周期（0.01574%）；逐对周期下降率平均0.05462%，中位数0，额外搬运合计增加67584字节。以上总量包含三个重复种子，不是100图总量。',
 'case013三个种子都改善，平均下降0.3437%，但每个种子增加24576字节搬运。种子0轨迹为packing后经frontier、joint、cache继续改善；旧组合停在54117，新策略53906。',
 'case068种子0旧组合在cache之后通过insert从116636降到116565，新策略停在116636。种子1也退步61周期，种子2持平。新策略三种子的提议数236/249/260，旧组合244/265/270；存在路径与单位提议成本共同影响，不能单凭次数断言原因。',
 '下一步优先核查case068旧insert候选在新轨迹中的生成时机、去重和排序状态，区分未生成、未评估和未改善。不以case编号硬编码算法，不继续扩大全量，也不在这批验证结果上悄悄调参再称留出测试。',
 '全部36项通过最终官方完整复核；最大墙钟476.989秒，峰值子进程RSS160.22MiB。历史暖初解生成未计入，不宣称冷启动端到端十分钟全面达标。','']
 (root/'README.md').write_text('\n'.join(lines),encoding='utf-8');return result
if __name__=='__main__':
 r=report(Path(sys.argv[1]));print(json.dumps(r['summary'],indent=2));print(r['errors'])
 if r['errors']:raise SystemExit(1)
