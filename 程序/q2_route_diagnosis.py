"""Explain r05 candidate opportunity losses from immutable saved trajectories."""
import csv,json,statistics,time
from collections import Counter
from q1_io import ROOT,sha,write_json
from q2_full_campaign import OUT as SOURCE,read

OUT=ROOT/'图表/runs/20260924-A-q2-diagnosis-r06'


def best(rows):
    return min((r for r in rows if r['status']=='ok'),key=lambda r:(r['makespan'],r['bytes']))


def main():
    assert not OUT.exists();OUT.mkdir(parents=True);started=time.perf_counter()
    profiles={r['case']:r for r in read(ROOT/'审查/证据/20260924-A-q2-compliance-r04-v2/structure_screen.json')}
    records=[];files={}
    for i in range(1,101):
        for k in range(2,6):
            searches={};rows={}
            for arm in ['legacy','routed']:
                folder=SOURCE/f'cases/case_{i:03}/{k}/{arm}'
                for name in ['search.json','row.json']:
                    p=folder/name;files[p.relative_to(ROOT).as_posix()]=sha(p.read_bytes())
                searches[arm]=read(folder/'search.json');rows[arm]=read(folder/'row.json')
            l,r=(searches[a]['evaluations'] for a in ['legacy','routed'])
            assert len(l)==len(r)==12
            assert [x['plan_sha256'] for x in l[:6]]==[x['plan_sha256'] for x in r[:6]]
            lb,rb=best(l[:8]),best(r[:8]);lf,rf=best(l),best(r)
            for arm,b,f in [('legacy',lb,lf),('routed',rb,rf)]:
                assert b['plan_sha256']==searches[arm]['base_plan_sha256']
                assert b['makespan']==searches[arm]['base_makespan']
                assert f['makespan']==rows[arm]['makespan']
            gl=lb['makespan']-lf['makespan'];gr=rb['makespan']-rf['makespan']
            gap=rf['makespan']-lf['makespan'];base_gap=rb['makespan']-lb['makespan']
            assert gap==base_gap+gl-gr
            same=lb['plan_sha256']==rb['plan_sha256']
            if same:
                assert [(x['plan_sha256'],x['makespan'],x['bytes']) for x in l[8:]]==[(x['plan_sha256'],x['makespan'],x['bytes']) for x in r[8:]]
                assert gap==0
            outcome='loss' if gap>0 else 'win' if gap<0 else 'tie'
            kind=('base_worse' if base_gap>0 else 'J_after_equal_base' if base_gap==0 else 'J_despite_better_base') if gap>0 else 'not_loss'
            record=dict(case=i,cores=k,outcome=outcome,loss_type=kind,legacy_base=lb['makespan'],routed_base=rb['makespan'],
                        legacy_final=lf['makespan'],routed_final=rf['makespan'],base_gap=base_gap,legacy_J_gain=gl,routed_J_gain=gr,
                        final_gap=gap,J_gain_difference=gl-gr,same_anchor=same,legacy_base_name=lb['name'],routed_base_name=rb['name'],
                        legacy_base_slot=next(j+1 for j,x in enumerate(l[:8]) if x is lb),routed_base_slot=next(j+1 for j,x in enumerate(r[:8]) if x is rb),
                        legacy_base_missing_from_routed=lb['plan_sha256'] not in {x['plan_sha256'] for x in r[:8]},
                        old_base_alone_beats_routed_final=lb['makespan']<rf['makespan'],ops=profiles[i]['ops'],largest_fraction=profiles[i]['largest_fraction'],
                        legacy_final_bytes=lf['bytes'],routed_final_bytes=rf['bytes'])
            # Conditional replay of two fixed 8+4 menus, not a new scored result.
            # Reuse J only when the complete chosen anchor hash matches a saved anchor.
            for label,menu in [('keep_old_chain',l[:6]+[l[6],r[7]]),('keep_old_depth',l[:6]+[r[6],l[7]])]:
                anchor=best(menu);source=next((a for a,b in [('legacy',lb),('routed',rb)] if b['plan_sha256']==anchor['plan_sha256']),None)
                record[label+'_anchor_known']=source is not None
                if source:
                    final=best(menu+searches[source]['evaluations'][8:])
                    record[label+'_cycles']=final['makespan'];record[label+'_bytes']=final['bytes'];record[label+'_J_source']=source
                else:
                    record[label+'_cycles']=None;record[label+'_bytes']=None;record[label+'_J_source']=None
            records.append(record)
    losses=[r for r in records if r['outcome']=='loss']
    s=dict(status='POSTHOC_DIAGNOSIS_NOT_NEW_BENCHMARK',configs=400,losses=len(losses),
           outcomes=dict(Counter(r['outcome'] for r in records)),loss_types=dict(Counter(r['loss_type'] for r in losses)),
           loss_base_slots=dict(Counter(r['legacy_base_slot'] for r in losses)),
           loss_base_gap_sum=sum(r['base_gap'] for r in losses),loss_J_gain_difference_sum=sum(r['J_gain_difference'] for r in losses),
           loss_final_gap_sum=sum(r['final_gap'] for r in losses),same_anchor_configs=sum(r['same_anchor'] for r in records),
           old_base_alone_recovers=sum(r['old_base_alone_beats_routed_final'] for r in losses),
           conditional_replays={},global_evaluator_calls=0,seconds=time.perf_counter()-started)
    for label in ['keep_old_chain','keep_old_depth']:
        known=[r for r in records if r[label+'_anchor_known']]
        s['conditional_replays'][label]=dict(known=len(known),unknown=400-len(known),
            versus_routed=dict(Counter('win' if r[label+'_cycles']<r['routed_final'] else 'loss' if r[label+'_cycles']>r['routed_final'] else 'tie' for r in known)),
            original_loss_configs_recovered=sum(r[label+'_cycles']<=r['legacy_final'] for r in known if r['outcome']=='loss'),
            caveat='Only exact saved-anchor matching permits conditional J reuse; no claim about new-anchor rows, solver time, independent confirmation or adoption.')
    write_json(OUT/'source_manifest.json',dict(files=files,source_summary_sha256=sha((SOURCE/'summary.json').read_bytes()),script_sha256=sha(__import__('pathlib').Path(__file__).read_bytes())))
    write_json(OUT/'summary.json',s);write_json(OUT/'records.json',records)
    with (OUT/'all_configs.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
    print(json.dumps(s,ensure_ascii=False,indent=2))
    print('LOSSES',json.dumps([{k:r[k] for k in ['case','cores','loss_type','base_gap','legacy_J_gain','routed_J_gain','legacy_base_name','routed_base_name','final_gap']} for r in losses],ensure_ascii=False))


if __name__=='__main__':main()
