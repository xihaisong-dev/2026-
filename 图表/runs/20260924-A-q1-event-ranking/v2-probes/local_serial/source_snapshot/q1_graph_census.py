"""Static all-case descriptors; descriptive, no tuning or evaluation calls."""
import argparse
from collections import Counter
import json
from pathlib import Path
from q1_io import PROCESSED,official,verify,sha,write_json


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args();manifest=verify();official()
    from q1_solver import Graph
    from evaluation_validation import read_evaluation_config
    from multicore_cut_evaluate_problem_1 import read_scene_a_config
    cfg=str(PROCESSED/'data/config.txt');settings=read_evaluation_config(cfg);waits=read_scene_a_config(cfg)
    rows=[]
    for item in sorted(manifest['cases'],key=lambda r:r['case']):
        p=PROCESSED/'data'/item['case'];raw=json.loads(p.read_text(encoding='utf-8-sig'));g=Graph(raw,settings,waits)
        loads=Counter()
        for o in g.ops.values():loads[o['pipe']]+=o['cycles']
        degree={u:len(g.pred[u]) for u in g.ops};width=sum(v==0 for v in degree.values());peak=width
        for u in g.order:
            width-=1
            for v in g.succ[u]:
                degree[v]-=1
                if degree[v]==0:width+=1
            peak=max(peak,width)
        cp=max(g.rank.values(),default=0);work=sum(loads.values())
        rows.append({'case':p.stem,'input_sha256':sha(p.read_bytes()),'raw_ops':len(raw['ops']),
            'noncopy_ops':len(g.ops),'tensors':len(raw['tensors']),'dependency_arcs':sum(len(v) for v in g.pred.values()),
            'fork_ops':sum(len(v)>1 for v in g.succ.values()),'join_ops':sum(len(v)>1 for v in g.pred.values()),
            'topological_frontier_peak':peak,'compute_critical_path_cycles':cp,'pipe_work_cycles':dict(loads),
            'work_over_compute_path':work/max(1,cp),'dominant_pipe_share':max(loads.values(),default=0)/max(1,work),
            'external_input_tensor_bytes':sum(size for size,_,ps,cs,_ in g.tensors if not ps and cs),
            'singleton_external_reread_bytes':sum(size*max(0,len(cs)-1) for size,_,ps,cs,_ in g.tensors if not ps),
            'max_tensor_consumer_fanout':max((len(cs) for _,_,_,cs,_ in g.tensors),default=0)})
    args.output.parent.mkdir(parents=True,exist_ok=True)
    if args.output.exists():raise FileExistsError(args.output)
    write_json(args.output,{'source_zip_sha256':manifest['source_sha256'],'cases':rows,
        'code_sha256':sha(Path(__file__).read_bytes()),'official_calls':0,
        'limitations':'frontier depends on traversal; singleton reread is hypothetical, not final copy bytes; work/path is not achievable speedup'})


if __name__=='__main__':main()
