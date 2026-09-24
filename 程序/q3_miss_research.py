"""Post-hoc byte accounting, not critical-path attribution or attainable gains."""
import gzip,json,heapq,hashlib
from collections import Counter,defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    rows=[];total=Counter();hashes={}
    for case in range(1,101):
        p=ROOT/f'图表/runs/20260924-A-q3-full-r02/case_{case:03}/5/selected_l2.json.gz'
        r=json.load(gzip.open(p,'rt',encoding='utf-8'))
        end={(c['core_id'],o['op_id']):o['end'] for c in r['per_core_timeline'] for o in c['ops']}
        ever=set();pending=defaultdict(list);counts=Counter()
        for e in r['cache_events']:
            tid=e['tensor_id'];now=e['time']
            if e['event']=='insert':ever.add(tid);continue
            if e['event']=='hit':counts['hit']+=e['size_bytes'];continue
            assert e['event']=='miss'
            q=pending[tid]
            while q and q[0]<=now:heapq.heappop(q)
            if e['size_bytes']>r['cache_capacity_bytes']:kind='oversized'
            elif tid in ever:kind='after_prior_insert'
            elif q:kind='overlapping_cold_read'
            else:kind='first_cold_read'
            counts[kind]+=e['size_bytes']
            heapq.heappush(q,end[e['core_id'],e['op_id']])
        assert sum(counts.values())==r['cache_stats']['hit_bytes']+r['cache_stats']['miss_bytes']
        rows.append(dict(case=case,bytes=dict(counts)));total.update(counts)
        hashes[str(p.relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest()
    out=ROOT/'审查/证据/20260924-A-q3/miss-research-r06.json';assert not out.exists()
    data=dict(scope='frozen Q3 full-r02, all 100 five-core selected plans; posthoc diagnostic only',
        definitions={'after_prior_insert':'miss following any prior insertion; includes concurrent re-reads after eviction',
        'overlapping_cold_read':'never inserted before; an earlier miss on same tensor has end > now',
        'first_cold_read':'eligible tensor with no prior insertion or unfinished earlier miss',
        'oversized':'individual transfer size exceeds current capacity'},
        bytes=dict(total),fractions_of_reads={k:v/sum(total.values()) for k,v in total.items()},
        warning='Traffic composition only. Does not imply criticality, feasible elimination or cycle savings.',rows=rows,sources=hashes)
    out.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({k:data[k] for k in ['bytes','fractions_of_reads']}))
if __name__=='__main__':main()
