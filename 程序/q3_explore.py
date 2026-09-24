"""Frozen-baseline pilot: event placement, input affinity and split placement.

Proxies propose only; unchanged official evaluation and physical audit decide.
Each family starts from the SAME frozen Q3 incumbent, with eight candidate calls.
"""
import argparse, copy, gzip, json, time
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from q1_io import ROOT, PROCESSED, sha, write_json
from q2_solver import SceneBGraph, context, owner_of
from q2_physical import legal_positions
from q2_guarded import structural
from q2_evaluator import key
from q3_solver import load, evaluate, audit
from q3_neighborhood import pool
from q3_run import dump_gz

PAIRS = [(1,3),(5,5),(19,3),(44,1),(46,1),(67,2),(84,2),(97,4),
         (12,5),(33,3),(72,4),(92,3)]
FAMILIES = ['ordinary','event','affinity','split']

def candidates(g, seed, result, family, budget):
    if family == 'ordinary':
        return pool(g, seed, budget=budget)
    mapping = {int(v):s for v,s in seed['node_to_subgraph'].items()}
    groups,_,_,_,incident,loads,ranks = context(g,mapping)
    owner = owner_of(seed)
    starts = {}; hot = Counter(); reads = defaultdict(dict)
    for core in result['per_core_timeline']:
        for op in core['ops']:
            s = op['subgraph_id']
            if s not in groups: continue
            starts[s] = min(starts.get(s,float('inf')),op['start'])
            if op['op']=='COPY_IN':
                if op.get('memory_path')=='DDR': hot[s] += op['duration']
                reads[op.get('cache_tensor_id')][s] = op['end']
    ranked = sorted(groups,key=lambda s:(-hot[s],-ranks[s],s))[:24]
    seen={key(seed)}; output=[]
    def add(plan, move):
        h=key(plan)
        if h in seen:return False
        try: structural(g,plan)
        except ValueError:return False
        seen.add(h);output.append(dict(plan=plan,move=move));return len(output)>=budget
    def insertion(base,s,c,target,kind):
        seqs,lo,hi=legal_positions(g,base,s,c)
        if lo>hi:return []
        positions=sorted(range(lo,hi+1),key=lambda i:(abs((starts.get(seqs[c][i],result['makespan']) if i<len(seqs[c]) else result['makespan'])-target),i))[:2]
        return [(dict(node_to_subgraph=dict(base['node_to_subgraph']),core_schedules=[q[:i]+[s]+q[i:] if j==c else q[:] for j,q in enumerate(seqs)]),dict(kind=kind,group=s,destination=c,position=i)) for i in positions]
    if family in ('event','affinity'):
        proposals=[]
        for s in ranked:
            affinities=Counter()
            for i in incident[s]:
                size,_,ps,cs,_=g.tensors[i]
                if not (cs & groups[s]):continue
                for other in {mapping[v] for v in cs}- {s}:affinities[other]+=size
            if family=='event':
                peers={v:t for ts in reads.values() if s in ts for v,t in ts.items() if v!=s}
                targets=sorted(peers,key=lambda v:(abs(peers[v]-starts.get(s,0)),v))[:2]
                for v in targets:
                    proposals.append((s,owner[s],peers[v],hot[s],v))
            else:
                for v in sorted(affinities,key=lambda v:(-affinities[v],v))[:2]:
                    proposals.append((s,owner[v],starts.get(v,0),affinities[v],v))
        proposals.sort(key=lambda x:(-x[3],x[0],x[4]))
        # First position for each move before trying the second position.
        queues=[insertion(seed,s,c,t,family) for s,c,t,_,_ in proposals]
        for offset in range(2):
            for q in queues:
                if len(q)>offset and add(*q[offset]):return output
    else:
        # A topological contiguous split preserves internal dependency direction.
        ranked=sorted((s for s in groups if len(groups[s])>=2),key=lambda s:(-max(loads[s].values(),default=0),-hot[s],s))[:12]
        queues=[]
        for s in ranked:
            nodes=sorted(groups[s],key=g.pos.__getitem__);new=max(groups)+1
            base=copy.deepcopy(seed)
            for v in nodes[len(nodes)//2:]:base['node_to_subgraph'][str(v)]=new
            c=owner[s];at=base['core_schedules'][c].index(s)
            base['core_schedules'][c].insert(at+1,new)
            try:structural(g,base)
            except ValueError:continue
            qs=[(base,dict(kind='split_in_place',group=s,new_group=new))]
            for dest in sorted(range(len(seed['core_schedules'])),key=lambda d:(sum(max(loads[v].values(),default=0) for v in seed['core_schedules'][d]),d)):
                if dest!=c:qs.extend(insertion(base,new,dest,starts.get(s,0),'split_migrate'))
            # Prefer split+migration; in-place is a separate candidate.
            queues.append(qs[1:]+qs[:1])
        for offset in range(max(map(len,queues),default=0)):
            for q in queues:
                if len(q)>offset and add(*q[offset]):return output
    return output

def job(args):
    case,n,baseline,out,budget=args;start=time.perf_counter()
    root=Path(baseline)/f'case_{case:03}/{n}';dest=Path(out)/f'case_{case:03}/{n}'
    dest.mkdir(parents=True,exist_ok=False)
    raw=json.loads((PROCESSED/f'data/case_{case:03}.json').read_text(encoding='utf-8-sig'))
    seed=json.loads((root/f'case_{case:03}_multicore_res.json').read_text(encoding='utf-8'))
    metrics=json.loads((root/'metrics.json').read_text(encoding='utf-8'))
    settings,delay,cache,_=load();g=SceneBGraph(raw,settings,delay)
    anchor=evaluate(raw,seed,settings,delay,cache)
    assert anchor['makespan']==metrics['selected_l2']
    def objective(r):return r['makespan'],r['data_movement_bytes']['added_copy_bytes']
    answer=dict(case=case,cores=n,baseline=anchor['makespan'],families={})
    for family in FAMILIES:
        best=seed;result=anchor;rows=[];t=time.perf_counter()
        proposals=candidates(g,seed,anchor,family,budget)
        for item in proposals:
            p=item['plan']
            try:
                r=evaluate(raw,p,settings,delay,cache)
                accepted=objective(r)<objective(result)
                if accepted:best,result=p,r
                rows.append(dict(move=item['move'],makespan=r['makespan'],added_bytes=objective(r)[1],hit_rate=r['cache_stats']['hit_rate'],accepted=accepted))
            except (RuntimeError,ValueError) as exc:rows.append(dict(move=item['move'],error=str(exc)))
        replay=evaluate(raw,best,settings,delay,cache);assert replay==result
        checks=audit(raw,best,replay,settings,delay)
        folder=dest/family;folder.mkdir()
        write_json(folder/'plan.json',best);dump_gz(folder/'result.json.gz',replay)
        entry=dict(makespan=replay['makespan'],ratio=anchor['makespan']/replay['makespan'],hit_rate=replay['cache_stats']['hit_rate'],added_bytes=objective(replay)[1],candidate_calls=len(rows),seconds=time.perf_counter()-t,checks=checks,evaluations=rows,plan_sha256=key(best))
        write_json(folder/'search.json',entry)
        answer['families'][family]={k:v for k,v in entry.items() if k not in ('checks','evaluations')}
    answer['seconds']=time.perf_counter()-start;write_json(dest/'metrics.json',answer)
    return answer

def main():
    p=argparse.ArgumentParser();p.add_argument('--baseline',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--workers',type=int,default=1);p.add_argument('--budget',type=int,default=8);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False)
    frozen={str(f.relative_to(a.baseline)):sha(f.read_bytes()) for f in sorted(a.baseline.rglob('*')) if f.is_file() and (f.name=='metrics.json' or f.name.endswith('_multicore_res.json'))}
    assert len(frozen)==1000
    write_json(a.output/'contract.json',dict(baseline=str(a.baseline),baseline_hashes=frozen,discovery=PAIRS[:8],validation=PAIRS[8:],families=FAMILIES,budget=a.budget,workers=a.workers,source_sha256=sha(Path(__file__).read_bytes()),promotion_rule='one new family: discovery >=3 strict wins and mean ratio>=1.005; validation >=2 wins and mean ratio>=1.002; all official replay/FIFO/global-memory audits pass. No full expansion otherwise.',stage_gate='NOT_RUN'))
    rows=[];errors=[]
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        futures={pool.submit(job,(c,n,str(a.baseline),str(a.output),a.budget)):(c,n) for c,n in PAIRS}
        for f in as_completed(futures):
            try:
                row=f.result();rows.append(row);print(json.dumps(row),flush=True)
            except Exception as exc:errors.append(dict(pair=futures[f],error=repr(exc)));print(errors[-1],flush=True)
            write_json(a.output/'progress.json',rows);write_json(a.output/'errors.json',errors)
    assert frozen=={x:sha((a.baseline/x).read_bytes()) for x in frozen}
    write_json(a.output/'completion.json',dict(complete=not errors,count=len(rows),baseline_unchanged=True,errors=errors))
    if errors:raise RuntimeError(errors)

if __name__=='__main__':main()
