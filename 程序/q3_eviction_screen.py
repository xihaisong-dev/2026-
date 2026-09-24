"""Choose mechanism-conditioned cases from frozen traces, before new scoring."""
import argparse,gzip,json
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
from q1_io import PROCESSED,write_json,sha
from q3_solver import load,audit_cache
from q2_solver import SceneBGraph
from q3_eviction import witnesses,proposals
PRIOR={1,5,7,9,12,16,19,21,23,27,31,33,36,38,41,44,46,49,53,58,61,64,67,72,76,81,84,87,89,92,95,97,98,99}
def job(arg):
    case,root=arg;src=Path(root)/f'case_{case:03}/5'
    raw=json.loads((PROCESSED/f'data/case_{case:03}.json').read_text());plan=json.loads((src/f'case_{case:03}_multicore_res.json').read_text())
    r=json.load(gzip.open(src/'selected_l2.json.gz','rt'));audit_cache(r);s,d,_,_=load()
    es,err=witnesses(raw,plan,r,s,d);g=SceneBGraph(raw,s,d)
    availability={m:bool(proposals(g,plan,r,es,m,1)) for m in ['consumer','source','joint']}
    return dict(case=case,cores=5,count=len(es),critical_reread_share=sum(e['duration'] for e in es)/r['makespan'],availability=availability,witnesses=es,reconstruction_error=err,source_sha256=sha((src/'selected_l2.json.gz').read_bytes()))
def main():
    p=argparse.ArgumentParser();p.add_argument('--baseline',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--workers',type=int,default=12);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    write_json(a.output/'contract.json',dict(prior_cases=sorted(PRIOR),pool='100 frozen five-core plans',rule='Among cases with critical reread, explicit FIFO eviction and at least one legal candidate per arm, rank by critical reread duration / makespan descending, tie by case. First four prior cases are discovery; first four other cases validation. No scoring of new plans in screening.',scope='Mechanism-conditioned validation, not representative random sample or unseen raw data.'))
    rows=[]
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        fs={ex.submit(job,(case,str(a.baseline))):case for case in range(1,101)}
        for f in as_completed(fs):
            r=f.result();rows.append(r);write_json(a.output/f"case_{r['case']:03}.json",r)
            print(json.dumps({k:r[k] for k in ['case','count','availability','critical_reread_share']}),flush=True)
    eligible=sorted([r for r in rows if all(r['availability'].values())],key=lambda r:(-r['critical_reread_share'],r['case']))
    discovery=[[r['case'],5] for r in eligible if r['case'] in PRIOR][:4]
    validation=[[r['case'],5] for r in eligible if r['case'] not in PRIOR][:4]
    write_json(a.output/'selection.json',dict(discovery=discovery,validation=validation,eligible_count=len(eligible),screened=100,rule='contract.json',sufficient=len(discovery)==4 and len(validation)==4))
    assert len(discovery)==4 and len(validation)==4,'Insufficient eligible cases; do not silently replace criteria'
if __name__=='__main__':main()
