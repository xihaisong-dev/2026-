"""Verify disjoint calibration shards and freeze one policy for all 100 cases."""
import argparse,json,gzip,shutil
from pathlib import Path
from statistics import mean
from q1_io import ROOT,verify,sha,write_json
import q1_opportunity_report as audit


def resolve_source(source):
    p=Path(source)
    if p.exists():return p
    text=source.replace('\\','/')
    mapping={'ranking-full100-20260924-r01/validation/图表/runs/20260924-A-q1-ranking-full100':'图表/runs/20260924-A-q1-ranking-full100','memory-routing-20260924-r01/validation/runs':'图表/runs/20260924-A-q1-memory-routing/validation/runs','global-calibration-20260924-r01/runs':'图表/runs/20260924-A-q1-global-calibration/runs','event-ranking-20260924-r01/runs':'图表/runs/20260924-A-q1-event-ranking/server/runs'}
    for remote,local in mapping.items():
        if remote+'/' in text:return ROOT/local/text.split(remote+'/',1)[1]
    raise ValueError('Unknown verification source: '+source)

audit.local_source=resolve_source
load=audit.load
key=audit.key
folder=audit.folder


def path_for(run,phase,host):return run/('local' if host=='local' else 'server/runs')/(phase+'_'+host)


def read_rows(root,manifest):
    s,_=audit.check_run(root,manifest)
    return s,[dict(r,source=str(folder(root,r).resolve())) for r in s['runs']]


def compare(rows,base):
    result=audit.comparison(rows,base)
    result['mean_speedup']={str(k):{'trial':mean(r['speedup'] for r in rows if r['cores']==k),'control':mean(base[key(r)]['speedup'] for r in rows if r['cores']==k)} for k in [2,3,4,5]}
    result['acceptable']=result['time_reduction_pct']>=-1e-10 and all(v['trial']>=v['control']-1e-12 for v in result['mean_speedup'].values())
    return result


def select(run,output):
    output.mkdir(parents=True,exist_ok=False);m=verify();rows={};sources=None
    for phase in ['development','extension']:
        combined=[]
        for host in ['local','server']:
            s,r=read_rows(path_for(run,phase,host),m)
            if sources is None:sources=s['code_sha256']
            assert sources==s['code_sha256']
            combined+=r
        assert len(combined)==64
        assert len({(r['case'],r['cores'],r['config']) for r in combined})==64
        rows[phase]=combined
    d={(r['case'],r['cores']):r for r in rows['development'] if r['config']=='routes_event_rank'}
    cached=[r for r in rows['development'] if r['config']=='routes_event_reuse']
    assert len(d)==len(cached)==32
    signature=lambda st:[(r['candidate'],r['plan_sha256'],r['status'],r.get('evaluation_id')) for r in st['proposal_ledger']]
    for r in cached:
        a,b=Path(r['source']),Path(d[key(r)]['source'])
        assert (a/'plan.json').read_bytes()==(b/'plan.json').read_bytes()
        assert json.loads(gzip.decompress((a/'evaluation.json.gz').read_bytes()))==json.loads(gzip.decompress((b/'evaluation.json.gz').read_bytes()))
        st=load(a/'search.json');assert signature(st)==signature(load(b/'search.json'))
        assert st['preparation_reuse_stats']['global_evaluations']==st['official_calls']==11
    probe=run/'server/runs/crossplatform_server';s,p=read_rows(probe,m);assert len(p)==1 and s['code_sha256']==sources
    q=next(r for r in cached if key(r)==('case_009',2))
    a,b=Path(q['source']),Path(p[0]['source'])
    assert (a/'plan.json').read_bytes()==(b/'plan.json').read_bytes()
    assert json.loads(gzip.decompress((a/'evaluation.json.gz').read_bytes()))==json.loads(gzip.decompress((b/'evaluation.json.gz').read_bytes()))
    assert signature(load(a/'search.json'))==signature(load(b/'search.json'))
    result={'cache_equivalence':True,'crossplatform_equal':True,'code_sha256':sources,'comparisons':{}}
    selected=[]
    for phase in ['development','extension']:
        prevroot=ROOT/'图表/runs/20260924-A-q1-global-calibration/runs'/phase
        ps=load(prevroot/'summary.json');base={key(r):r for r in ps['runs'] if r['config']=='routes_event_guarded'}
        current=[r for r in rows[phase] if r['config']=='routes_event_reuse']
        for r in current:
            st=load(Path(r['source'])/'search.json');old=load(folder(prevroot,base[key(r)])/'search.json')
            names=lambda v:sorted((x['candidate'],x['compute_lower_bound'],x.get('local_prediction')) for x in v['structural_seed_stats'].get('ranked',[]))
            assert names(st)==names(old),'Candidate pool/local costs changed'
        result['comparisons'][phase]=compare(current,base);selected+=current
    oldroot=ROOT/'图表/runs/20260924-A-q1-ranking-full100';base={key(r):r for r in load(oldroot/'summary.json')['runs']}
    result['protection_passed']=all(r['makespan']<=base[key(r)]['makespan'] for r in cached if r['case'] in ['case_028','case_067'])
    passed=result['protection_passed'] and all(x['acceptable'] for x in result['comparisons'].values())
    result['variant']='routes_event_reuse' if passed else 'routes_gate_reuse'
    result['fallback_requires_equivalence_check']=not passed
    result['development_cache_runtime']={'uncached_seconds':sum(r['solve_seconds'] for r in d.values()),'cached_seconds':sum(r['solve_seconds'] for r in cached)}
    write_json(output/'selection.json',result)
    complete=selected if passed else []
    assert len(complete) in [0,96]
    done={r['case'] for r in complete};allcases=sorted(p.stem for p in (ROOT/'数据/processed/q1/data').glob('case_*.json'));assert len(allcases)==100
    pending=[c for c in allcases if c not in done]
    count=lambda c:sum(o['op'] not in ['COPY_IN','COPY_OUT'] for o in load(ROOT/'数据/processed/q1/data'/f'{c}.json')['ops'])
    order=sorted(pending,key=lambda c:(count(c),c));local=order[:30];server=list(reversed(order[30:]))
    assignments=[{'case':c,'cores':k,'host':'validation' if c in done else ('local' if c in local else 'server')} for c in allcases for k in [2,3,4,5]]
    manifest={'variant':result['variant'],'code_sha256':sources,'source_sha256':m['source_sha256'],'config_sha256':m['files']['data/config.txt'],'input_sha256':{c+'.json':m['files']['data/'+c+'.json'] for c in allcases},'hosts':{'local':{'pending_cases':local},'server':{'pending_cases':server}},'reuse_validation_records':complete,'assignments':assignments,'unique_configurations':400,'seed':0,'budget':12}
    assert not(set(local)&set(server)) and set(local)|set(server)|done==set(allcases)
    write_json(output/'full_manifest.json',manifest);print(json.dumps(result,ensure_ascii=False))


def collect(run,selection,output):
    import csv
    output.mkdir(parents=True,exist_ok=False);m=verify();assignment=load(selection/'full_manifest.json')
    rows=[dict(r,origin='validation') for r in assignment['reuse_validation_records']]
    for host in ['local','server']:
        expected=assignment['hosts'][host]['pending_cases']
        if not expected:continue
        stage=path_for(run,'full',host);summary,part=read_rows(stage,m)
        assert summary['code_sha256']==assignment['code_sha256']
        assert set(r['case'] for r in part)==set(expected)
        rows += [dict(r,origin=host) for r in part]
    assert len(rows)==400 and len({key(r) for r in rows})==400
    assert {r['config'] for r in rows}=={assignment['variant']}
    assert all(r['seed']==0 and r['evaluated_opportunities']==12 for r in rows)
    old_root=ROOT/'图表/runs/20260924-A-q1-ranking-full100'
    prior_summary=load(old_root/'summary.json')
    existing={(r['case'],r['cores']):r for r in prior_summary['runs']}
    shutil.copytree(old_root/'single',output/'single')
    snapshot=output/'source_snapshot';snapshot.mkdir()
    src=path_for(run,'development','local')/'source_snapshot'
    for name,h in assignment['code_sha256'].items():
        assert sha((src/name).read_bytes())==h
        shutil.copy2(src/name,snapshot/name)
    external_path=ROOT/'图表/runs/20260924-A-q1-ranking-analysis/all_case_results.csv'
    with external_path.open(encoding='utf-8-sig',newline='') as f:external={(r['case'],int(r['cores'])):r for r in csv.DictReader(f)}
    assert set(existing)==set(external)=={key(r) for r in rows}
    table=[];export=[]
    for k in [2,3,4,5]:
        group=[r for r in rows if r['cores']==k];assert len(group)==100
        for r in group:
            assert r['single_makespan']==existing[key(r)]['single_makespan']==int(external[key(r)]['single_makespan'])
            source=Path(r['source'])
            for name,h in r['artifacts'].items():assert sha((source/name).read_bytes())==h
            dest=output/f"{r['case']}_{k}cores_seed0_{r['config']}";shutil.copytree(source,dest)
            export.append(dict(case=r['case'],cores=k,single=r['single_makespan'],makespan=r['makespan'],speedup=r['speedup'],added_copy_bytes=r['added_copy_bytes'],partition_added_copy_bytes=r['partition_added_copy_bytes'],spill_added_copy_bytes=r['spill_added_copy_bytes'],old_makespan=existing[key(r)]['makespan'],reference_makespan=int(external[key(r)]['external_makespan']),solve_seconds=r['solve_seconds'],verification_seconds=r['verification_seconds'],host=r['origin']))
        total=sum(r['makespan'] for r in group);ref_total=sum(int(external[key(r)]['external_makespan']) for r in group)
        table.append(dict(cores=k,mean_speedup=mean(r['single_makespan']/r['makespan'] for r in group),old_mean_speedup=mean(existing[key(r)]['speedup'] for r in group),reference_mean_speedup=mean(float(external[key(r)]['external_speedup']) for r in group),total_cycles=total,reference_total_cycles=ref_total,reference_time_reduction_pct=100*(1-total/ref_total),added_bytes=sum(r['added_copy_bytes'] for r in group),vs_old=audit.comparison(group,existing),reference_wins=sum(r['makespan']<int(external[key(r)]['external_makespan']) for r in group),reference_ties=sum(r['makespan']==int(external[key(r)]['external_makespan']) for r in group),reference_losses=sum(r['makespan']>int(external[key(r)]['external_makespan']) for r in group)))
    result={'completed':True,'variant':assignment['variant'],'formal_default_changed':False,'cases':100,'configurations':400,'expected_runs':400,'single_references':prior_summary['single_references'],'seed':0,'code_sha256':assignment['code_sha256'],'source_zip_sha256':m['source_sha256'],'config_sha256':assignment['config_sha256'],'input_sha256':assignment['input_sha256'],'single_core_speedup':1,'per_core':table,'runs':rows,'failures':[],'budget':{'logical_search_scores':4400,'fixed_single_references':400,'reused_complete_validation_records':sum(r['origin']=='validation' for r in rows),'new_full_search_scores':11*sum(r['origin']!='validation' for r in rows),'final_original_replays_in_selected_records':sum(r['verification_calls'] for r in rows)},'max_solve_seconds':max(r['solve_seconds'] for r in rows),'over600':[(r['case'],r['cores'],r['solve_seconds']) for r in rows if r['solve_seconds']>600],'reference_csv_sha256':sha(external_path.read_bytes())}
    write_json(output/'summary.json',result)
    with (output/'all_case_results.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(export[0]));w.writeheader();w.writerows(sorted(export,key=lambda r:(r['case'],r['cores'])))
    lines=['# 事件排序及准备复用：100图全量结果','',f"冻结策略：{assignment['variant']}。每图每核唯一，不跨方案逐例择优。平均加速比为逐图固定单核/多核时间的算术平均。",'', '|核数|上一轮全量|本轮|参考工程|本轮总cycles|对参考胜/平/负|','|---|---:|---:|---:|---:|---|','|1|1|1|1|固定基准|—|']
    for r in table:lines.append(f"|{r['cores']}|{r['old_mean_speedup']:.6f}|{r['mean_speedup']:.6f}|{r['reference_mean_speedup']:.6f}|{r['total_cycles']}|{r['reference_wins']}/{r['reference_ties']}/{r['reference_losses']}|")
    lines += ['',f"预算：{result['budget']}。开发中未选中的不复用配置和跨平台探针属于额外诊断，另见selection，不混入400配置。",f"最大搜索耗时{result['max_solve_seconds']:.3f}秒，超过600秒{len(result['over600'])}组；单核冷生成和最终验证分列，不作为独占机器时间保证。",'','参考工程预算不同，成绩比较不证明同求解时间效率。主机/阶段只是任务归属，不能按结果选择记录。正式默认与main保持不变。逐例CSV给出Makespan、额外搬运及运行时间。']
    (output/'report.md').write_bytes(('\n'.join(lines)+'\n').encode());print(json.dumps({k:v for k,v in result.items() if k not in ['runs','code_sha256','input_sha256']},ensure_ascii=False))


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--selection',type=Path);a=ap.parse_args();collect(a.run,a.selection,a.output) if a.selection else select(a.run,a.output)

if __name__=='__main__':main()
