"""Diagnostic parameter sweep only; never changes the official config file."""
import argparse,json,time
from pathlib import Path
from q1_io import PROCESSED,write_json
from q3_solver import load,evaluate,audit_cache
from q3_run import SEEDS


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False);s,d,c,provenance=load();rows=[]
    write_json(a.output/'contract.json',dict(role='diagnostic_not_official_fixed_config',cases=[1,5,19],cores=[3,5],
                capacity_values=[0,262144,524288,1048576,2097152],bandwidth_values=[60,125,250,500],provenance=provenance))
    for case in [1,5,19]:
        raw=json.loads((PROCESSED/f'data/case_{case:03}.json').read_text(encoding='utf-8-sig'))
        for n in [3,5]:
            plan=json.loads((SEEDS/f'{n}cores/case_{case:03}_multicore_res.json').read_text(encoding='utf-8-sig'))
            values=[(cap,250) for cap in [0,262144,524288,1048576,2097152]]+[(1048576,bw) for bw in [60,125,500]]
            for cap,bw in values:
                r=evaluate(raw,plan,s,d,dict(cache_capacity_bytes=cap,cache_bandwidth_bytes_per_cycle=bw));check=audit_cache(r)
                rows.append(dict(case=case,cores=n,capacity=cap,bandwidth=bw,makespan=r['makespan'],hit_rate=r['cache_stats']['hit_rate'],**check))
                write_json(a.output/'rows.json',rows)
            print(case,n,flush=True)
    write_json(a.output/'completion.json',dict(complete=True,count=len(rows)))


if __name__=='__main__':main()
