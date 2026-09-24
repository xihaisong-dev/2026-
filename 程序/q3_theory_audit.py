"""Read-only Q3 theory checks; parameter replays go to a new evidence directory."""
import argparse
import gzip
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from q1_io import ROOT, PROCESSED, sha, write_json, verify
from q3_solver import load, evaluate, audit_cache


def read(path):
    if str(path).endswith('.gz'):
        with gzip.open(path, 'rt', encoding='utf-8') as f: return json.load(f)
    return json.loads(path.read_text(encoding='utf-8'))


def original_lower(raw, n):
    """All original non-COPY ops must execute once; COPY costs relaxed to zero."""
    from schedule_step3 import _build_graph_views
    from q1_solver import topological
    _, _, pred, succ = _build_graph_views(raw['ops'], raw['edges'])
    weights={o['id']: max(1,o.get('cycles',1)) if o['op'] not in ('COPY_IN','COPY_OUT') else 0 for o in raw['ops']}
    sums=Counter()
    for o in raw['ops']: sums[o['pipe']]+=weights[o['id']]
    ends={}
    for v in topological(pred,succ): ends[v]=max((ends[u] for u in pred[v]),default=0)+weights[v]
    return max(max(ends.values(),default=0), max((v/n for v in sums.values()),default=0))


def row(result, raw):
    audit_cache(result)
    reads=[e for e in result['cache_events'] if e['event'] in ('hit','miss')]
    sizes={}; multiplicity=Counter()
    for e in reads:
        tid=e['tensor_id']; s=e['size_bytes']
        assert s>0 and sizes.get(tid,s)==s
        sizes[tid]=s; multiplicity[tid]+=1
    R=sum(e['size_bytes'] for e in reads)
    X=result['data_movement_bytes']['scheduled_copy_bytes']-R
    assert X>=0
    C=result['cache_capacity_bytes']; b=result['cache_bandwidth_bytes_per_cycle']; d=result['bandwidth_bytes_per_cycle']
    Hmax=sum((multiplicity[t]-1)*s for t,s in sizes.items() if s<=C)
    H=result['cache_stats']['hit_bytes']; N=result['cache_stats']['accesses']; nh=result['cache_stats']['hits']
    assert H<=Hmax
    z=min(Hmax,(R+X)*b/(b+d))
    relaxed_load=max((R+X-z)/d,z/b)
    compute=Counter()
    original_compute=Counter({o['id']:max(1,o.get('cycles',1)) for o in raw['ops'] if o['op'] not in ('COPY_IN','COPY_OUT')})
    actual_compute=Counter()
    for core in result['per_core_timeline']:
        for o in core['ops']:
            if o['op'] not in ('COPY_IN','COPY_OUT'):
                compute[core['core_id'],o['pipe']]+=o['duration']
                actual_compute[o['op_id']]+=o['duration']
    assert original_compute==actual_compute, 'Original compute preservation required by global lower bound'
    Lcomp=max(compute.values(),default=0)
    Lglobal=original_lower(raw,result['num_cores'])
    Lrelax=max(relaxed_load,Lcomp,Lglobal)
    Ltrace=max((R+X-H)/d,H/b,Lcomp,Lglobal)
    T=result['makespan']
    assert 0<Lglobal<=Lrelax+1e-6<=Ltrace+1e-6 and Ltrace<=T+1e-6, (Lglobal,Lrelax,Ltrace,T)
    return dict(makespan=T,capacity=C,bandwidth=b,read_bytes=R,write_bytes=X,
                hit_bytes=H,read_count=N,hit_count=nh,hit_rate_bytes=H/R if R else 0,
                hit_rate_count=nh/N if N else 0,optimistic_hit_bytes=Hmax,
                balanced_hit_bytes=z,trace_byte_load_lower=Ltrace,plan_relaxation_lower=Lrelax,
                universal_compute_lower=Lglobal,relaxation_gap=T/Lrelax-1)


def exact_detail(raw,plan,result,s,d):
    from multicore_cut_evaluate_problem_3 import _build_scene_b_tasks
    from schedule_step3 import _op_duration
    from q2_bottleneck_j import analyze
    tasks,links,*_= _build_scene_b_tasks(raw,plan,s['bandwidth'],s['capacity'])
    obs=analyze(tasks,links,result,d,s['bandwidth'])
    entries={(c['core_id'],o['op_id']):o for c in result['per_core_timeline'] for o in c['ops']}
    works=Counter(); cp=Counter()
    for (c,i),o in entries.items():
        path=o.get('memory_path'); task=tasks[c]
        if path in ('DDR','CACHE_READ'):
            bw=result['cache_bandwidth_bytes_per_cycle'] if path=='CACHE_READ' else s['bandwidth']
            works[path]+=_op_duration(task['op_by_id'][i],task['in_tids'],task['out_tids'],task['tensor_by_id'],bw)
    for v in obs['critical_chain']:
        o=entries[v['core'],v['op']]
        cp[o.get('memory_path',o['pipe'])]+=o['duration'];cp['sync']+=v['incoming_lag']
    assert sum(cp.values())==result['makespan'] and max(works.values(),default=0)<=result['makespan']+1e-6
    return dict(service_work_cycles=dict(works),critical_chain_cycles=dict(cp),start_residual=obs['start_reconstruction_max_error'])


def event_diff(a,b):
    def inspect(r):
        records={}; last_fill={}; last_evict={}
        for index,e in enumerate(r['cache_events']):
            tid=e['tensor_id']
            if e['event']=='insert':
                last_fill[tid]=dict(time=e['time'],event_index=index,core=e['core_id'],op=e['op_id'])
                last_evict.pop(tid,None)
                for old in e['evicted_tensor_ids']:
                    last_evict[old]=dict(time=e['time'],event_index=index,evicting_tensor=tid,core=e['core_id'],op=e['op_id'])
            else:
                records[e['core_id'],e['op_id']]=dict(event=e,last_fill=last_fill.get(tid),last_eviction=last_evict.get(tid))
        return records
    aa,bb=inspect(a),inspect(b)
    assert aa.keys()==bb.keys()
    changed=[dict(core=k[0],op=k[1],a=aa[k],b=bb[k]) for k in aa if aa[k]['event']['event']!=bb[k]['event']['event']]
    changed.sort(key=lambda x:min(x['a']['event']['time'],x['b']['event']['time']))
    def signature(e):return e['event'],e['core_id'],e['op_id'],e['tensor_id'],e.get('evicted_tensor_ids',[])
    first=None
    for i,(x,y) in enumerate(zip(a['cache_events'],b['cache_events'])):
        if signature(x)!=signature(y):first=dict(index=i,a=x,b=y);break
    return dict(changed_hit_decisions=len(changed),first_event_order_or_state_difference=first,first_changed_reads=changed[:3])


def freeze_check():
    f=read(ROOT/'审查/证据/20260924-A-q3/baseline-freeze-r02.json')
    for name,h in f['files'].items(): assert sha((ROOT/f['baseline']/name).read_bytes())==h
    p=read(ROOT/'审查/证据/20260924-A-q3/parameter-freeze-before-r03.json')
    for name,h in p.items(): assert sha((ROOT/name).read_bytes())==h
    return dict(baseline_files=len(f['files']),parameter_files=len(p))


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    a.output.mkdir(parents=True,exist_ok=False)
    verify();before=freeze_check();s,d,c,_=load();sources={};rows=[]
    def source(p):sources[str(p.relative_to(ROOT))]=sha(p.read_bytes());return read(p)
    for case in range(1,101):
        raw=source(PROCESSED/f'data/case_{case:03}.json')
        p=ROOT/f'图表/runs/20260924-A-q3-full-r02/case_{case:03}/5/selected_l2.json.gz'
        r=source(p);rr=row(r,raw);rr['case']=case;rows.append(rr)
    agg=dict(mean_byte_hit_rate=mean(x['hit_rate_bytes'] for x in rows),pooled_byte_hit_rate=sum(x['hit_bytes'] for x in rows)/sum(x['read_bytes'] for x in rows),
             mean_count_hit_rate=mean(x['hit_rate_count'] for x in rows),pooled_count_hit_rate=sum(x['hit_count'] for x in rows)/sum(x['read_count'] for x in rows),
             min_plan_bound_ratio=min(x['makespan']/x['plan_relaxation_lower'] for x in rows),max_plan_bound_ratio=max(x['makespan']/x['plan_relaxation_lower'] for x in rows))
    print(json.dumps(agg),flush=True)
    parameter_rows=[]
    for dirname in ['20260924-A-q3-parameter-reopt-r01','20260924-A-q3-parameter-followup-r01']:
        for p in sorted((ROOT/'图表/runs'/dirname).glob('case_*/*/fixed.json.gz')):
            case=int(p.parent.parent.name.split('_')[1]);raw=read(PROCESSED/f'data/case_{case:03}.json')
            for name in ['fixed.json.gz','selected.json.gz']:
                q=p.parent/name;rr=row(source(q),raw);rr.update(case=case,scope=name);parameter_rows.append(rr)
    replays={};details={}
    from q3_run import SEEDS, dump_gz
    for case,n,values in [(5,5,[(1048576,b) for b in [60,125,250,500]]),(44,1,[(C,250) for C in [65536,131072]])]:
        raw=source(PROCESSED/f'data/case_{case:03}.json');plan=source(SEEDS/f'{n}cores/case_{case:03}_multicore_res.json')
        for C,b in values:
            key=f'case{case}_C{C}_b{b}'
            result=evaluate(raw,plan,s,d,dict(cache_capacity_bytes=C,cache_bandwidth_bytes_per_cycle=b))
            r=row(result,raw);r.update(exact_detail(raw,plan,result,s,d));details[key]=r;replays[key]=result
            dump_gz(a.output/(key+'.json.gz'),result)
            if case==5:
                old=source(ROOT/f'图表/runs/20260924-A-q3-sensitivity-r01/bandwidth_counterexample/bw_{b}.json.gz')
                assert json.loads(json.dumps(result))==old
            print(key,result['makespan'],flush=True)
    diffs=dict(bandwidth=event_diff(replays['case5_C1048576_b60'],replays['case5_C1048576_b250']),
               capacity=event_diff(replays['case44_C65536_b250'],replays['case44_C131072_b250']))
    after=freeze_check();assert before==after
    write_json(a.output/'evidence.json',dict(scope='Theory audit only; no optimization or expansion',aggregate=agg,five_core_rows=rows,
               parameter_rows=parameter_rows,replays=details,event_differences=diffs,freeze_checks=after,sources=sources,
               source_hash=sha(Path(__file__).read_bytes()),official_sources={str(p.relative_to(PROCESSED)):sha(p.read_bytes()) for p in (PROCESSED/'code').glob('*.py')},
               checks=dict(fifo_ledgers=len(rows)+len(parameter_rows)+len(details),official_replays=6,old_bandwidth_full_replay_equal=4,all_lower_bounds_pass=True)))
    print('DONE',len(rows),len(parameter_rows),flush=True)


if __name__=='__main__':main()
