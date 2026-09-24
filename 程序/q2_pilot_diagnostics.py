"""Posthoc physical diagnostics; never feeds candidates back into frozen pilot."""
import gzip,json
from collections import defaultdict,Counter
from q1_io import ROOT,PROCESSED,write_json,sha
from q2_evaluator import load
from q2_physical import PhysicalScorer
from q2_bottleneck_j import diagnose
from q2_main_campaign import OUT


def main():
    dest=OUT/'posthoc_diagnostics.json'
    if dest.exists():raise FileExistsError(dest)
    settings,delay,_=load();rows=[]
    # Include the validation regression, without changing any search outcome.
    for phase,i,k in [('development',48,5),('development',50,4),('validation',12,3)]:
        raw=json.loads((PROCESSED/f'data/case_{i:03}.json').read_text())
        for mode in ['ordinary','guided']:
            folder=OUT/phase/f'case_{i:03}/{k}/{mode}'
            plan=json.loads((folder/f'case_{i:03}_multicore_res.json').read_text())
            with gzip.open(folder/'evaluation.json.gz','rt',encoding='utf-8') as f:result=json.load(f)
            physical=PhysicalScorer(raw,settings,delay)
            lives=physical.actual_lifetimes(plan,result)
            d=diagnose(raw,plan,result,settings,delay)
            busy=defaultdict(int)
            for core in result['per_core_timeline']:
                for op in core['ops']:busy[core['core_id'],op['pipe']]+=op['duration']
            top=sorted(busy,key=lambda x:-busy[x])[:4]
            chain_time=Counter();lags=Counter()
            for op in d['critical_chain']:
                chain_time[op['incoming_kind']]+=op['end']-op['start']
                lags[op['incoming_kind']]+=op['incoming_lag']
            assert sum(chain_time.values())+sum(lags.values())==result['makespan']
            rows.append(dict(case=i,cores=k,mode=mode,makespan=result['makespan'],
                traffic=result['data_movement_bytes'],start_error=d['start_reconstruction_max_error'],
                chain_duration_by_incoming_constraint=dict(chain_time),chain_lags=dict(lags),
                hol_count=len(d['hol']),largest_hol_opportunity=max((x['opportunity_cycles'] for x in d['hol']),default=0),
                ddr_overlapping_extra_cycles=d['ddr_observed_extra_cycles'],
                busiest_pipes=[dict(core=c,pipe=p,busy_cycles=busy[c,p],utilization=busy[c,p]/result['makespan']) for c,p in top],
                physical_lifetimes={c:{name:v for name,v in profile.items() if name!='intervals'} for c,profile in lives.items()},
                preparation_calls=physical.prepare_calls+1))
    write_json(dest,dict(status='posthoc_explanation_only',source_sha256=sha(__import__('pathlib').Path(__file__).read_bytes()),
        caveat='Incoming labels explain one realized chain, not additive causal loss. HOL and concurrent DDR delays are not guaranteed recoverable makespan. Residency checked against official capacity.',rows=rows))
    print(json.dumps(rows,ensure_ascii=False))


if __name__=='__main__':main()
