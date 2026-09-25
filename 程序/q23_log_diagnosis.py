"""Read-only historical candidate accounting; no counterfactual causal claims."""
import json
from collections import defaultdict,Counter
from pathlib import Path

def read(p):return json.loads(p.read_text(encoding='utf-8'))

def summarize(root):
    rows={(r['case'],r['arm']):r for r in map(read,(root/'q2/rows').glob('*.json'))}
    losses=[i for i in range(1,101) if rows[i,'protected']['makespan']>rows[i,'ordinary_extended']['makespan']]
    output={'loss_cases':losses,'cases':[],'aggregates':{},'limitations':[
        'Recorded duplicate seconds are zero: generation/hash cost is not measured per duplicate.',
        'Historical adaptive paths differ; observed gains do not establish counterfactual causality.',
        'Q3 omitted duplicate rows; infer only attempted-family minus scored calls when final counters exist.',
        'Evaluator seconds are not whole search budget; generation, serialization and uncompleted calls remain unassigned.']}
    for scope,ids in [('loss16',losses),('all100',list(range(1,101)))]:
        for arm in ['ordinary_extended','protected']:
            stats=defaultdict(Counter)
            for i in ids:
                search=read(root/f'q2/jobs/case_{i:03}_{arm}/search.json');best=None
                for r in search['evaluations']:
                    st=stats[r['name']];st['attempts']+=1;st[r['status']]+=1;st['recorded_seconds']+=r.get('seconds',0)
                    if r.get('accepted'):st['accepted']+=1
                    if r['status']=='ok':
                        obj=(r['makespan'],r['added_copy_bytes'])
                        if best is not None:
                            st['accepted_cycle_gain']+=max(0,best[0]-obj[0])
                            if obj[0]==best[0] and obj[1]<best[1]:st['same_cycle_byte_gain']+=best[1]-obj[1]
                        best=min(best,obj) if best else obj
            total=sum(v['recorded_seconds'] for v in stats.values())
            output['aggregates'][scope+'_'+arm]={k:dict(v,duplicate_rate=v['duplicate']/v['attempts'],recorded_time_share=v['recorded_seconds']/total) for k,v in stats.items()}
    for i in losses:
        a=read(root/f'q2/jobs/case_{i:03}_ordinary_extended/search.json')['evaluations'];b=read(root/f'q2/jobs/case_{i:03}_protected/search.json')['evaluations']
        prefix=0
        for x,y in zip(a,b):
            if (x.get('plan_sha256'),x.get('status'))!=(y.get('plan_sha256'),y.get('status')):break
            prefix+=1
        output['cases'].append(dict(case=i,ordinary=rows[i,'ordinary_extended']['makespan'],protected=rows[i,'protected']['makespan'],
            regression_cycles=rows[i,'protected']['makespan']-rows[i,'ordinary_extended']['makespan'],common_prefix=prefix,
            ordinary_joint_scored=sum(r['name']=='joint' and r['status']=='ok' for r in a),
            protected_joint_scored=sum(r['name']=='joint' and r['status']=='ok' for r in b)))
    return output

if __name__=='__main__':
    import sys
    p=Path(sys.argv[1]);r=summarize(p/'logs');(p/'diagnosis.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
