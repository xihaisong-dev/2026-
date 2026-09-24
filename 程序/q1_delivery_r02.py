"""Export the adopted 100-case Q1 evidence; never recompute or select best across runs."""
import csv, gzip, json, shutil
from pathlib import Path
from statistics import mean
from q1_io import ROOT, PROCESSED, official, verify, sha, write_json

RUN = ROOT / '图表/runs/20260924-A-q1-event-ranking-full100'
OUT = ROOT / '图表/runs/20260924-A-q1-delivery-r02'

def main():
    verify(); official()
    from singlecore_evaluate import build_singlecore_plan
    from stub_multicore_cut_and_schedule import derive_multicore_plan
    from evaluation_validation import validate_task_order
    OUT.mkdir(exist_ok=True)
    rows = []
    source = list(csv.DictReader((RUN/'all_case_results.csv').open(encoding='utf-8-sig')))
    assert len(source) == 400 and len({(r['case'],r['cores']) for r in source}) == 400
    index = {(r['case'],int(r['cores'])): r for r in source}
    for i in range(1,101):
        case = f'case_{i:03d}'
        raw = json.loads((PROCESSED/'data'/f'{case}.json').read_text(encoding='utf-8-sig'))
        single = json.loads((RUN/'single'/case/'row.json').read_text(encoding='utf-8'))
        for k in range(1,6):
            folder = RUN/'single'/case if k==1 else RUN/f'{case}_{k}cores_seed0_routes_gate_reuse'
            result = json.loads(gzip.decompress((folder/'evaluation.json.gz').read_bytes()))
            plan = build_singlecore_plan(raw) if k==1 else json.loads((folder/'plan.json').read_text(encoding='utf-8'))
            validate_task_order(derive_multicore_plan(raw,plan))
            r = dict(case=case,cores=k,config='fixed_single' if k==1 else 'routes_gate_reuse',
                makespan=result['makespan'],added_copy_bytes=result['data_movement_bytes']['added_copy_bytes'],
                single_makespan=single['makespan'],speedup=single['makespan']/result['makespan'],
                source=folder.relative_to(ROOT).as_posix(),evaluation_sha256=sha((folder/'evaluation.json.gz').read_bytes()))
            if k>1:
                saved=index[case,k]
                assert r['makespan']==int(saved['makespan']) and r['added_copy_bytes']==int(saved['added_copy_bytes'])
            else:
                assert r['makespan']==single['makespan']
            dest=OUT/'solutions'/f'{k}cores';dest.mkdir(exist_ok=True,parents=True)
            write_json(dest/f'{case}_multicore_res.json',plan)
            rows.append(r)
    with (OUT/'all_case_results.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
    aggregate=[]
    for k in range(1,6):
        current=[r for r in rows if r['cores']==k]; old=[r for r in source if int(r['cores'])==k]
        total=sum(r['makespan'] for r in current)
        previous=sum(int(r['old_makespan']) for r in old) if k>1 else total
        aggregate.append(dict(cores=k,cases=100,mean_speedup=mean(r['speedup'] for r in current),
            total_cycles=total,previous_total_cycles=previous,
            reduction_vs_previous_pct=100*(previous-total)/previous,
            previous_mean_speedup=mean(int(r['single'])/int(r['old_makespan']) for r in old) if k>1 else 1,
            total_added_copy_bytes=sum(r['added_copy_bytes'] for r in current)))
    write_json(OUT/'aggregate.json',aggregate)
    write_json(OUT/'best_cases.json',{str(k):[r for r in rows if r['cores']==k and r['speedup']==max(x['speedup'] for x in rows if x['cores']==k)] for k in range(1,6)})
    with (OUT/'aggregate.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(aggregate[0]),lineterminator='\n');w.writeheader();w.writerows(aggregate)
    tex=['% Requires longtable and booktabs; cycles and bytes, fixed single baseline.',r'\begin{longtable}{lrrrr}',r'\caption{问题一全部算例的官方评价结果}\\',r'\toprule 算例 & 核数 & Makespan & 额外搬运量 & 加速比 \\',r'\midrule\endfirsthead',r'\toprule 算例 & 核数 & Makespan & 额外搬运量 & 加速比 \\\midrule\endhead']
    for r in rows:
        tex.append(f"{r['case'].replace('_',r'\_')} & {r['cores']} & {r['makespan']} & {r['added_copy_bytes']} & {r['speedup']:.6f} \\")
        tex[-1]+='\\'
    tex += [r'\bottomrule',r'\end{longtable}']
    (OUT/'appendix_results.tex').write_text('\n'.join(tex)+'\n',encoding='utf-8')
    write_json(OUT/'export_audit.json',dict(rows=500,unique_case_core_pairs=500,legal_plans=500,
        raw_result_numeric_matches=500,source_commit='4d693a2efa5a1f4373a0f553789bf324115481aa',
        source_summary_sha256=sha((RUN/'summary.json').read_bytes()),input_manifest_sha256=sha((PROCESSED/'manifest.json').read_bytes())))
    print(json.dumps(aggregate,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
