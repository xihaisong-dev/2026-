"""Replay one fixed pool through uncached and cached exact engines."""
import argparse,gzip,json,time
from pathlib import Path
from q1_io import ROOT,write_json
from q1_staged_portfolio import context,original
from q1_task_reuse import TaskReuseEvaluator
from q1_fast_evaluator import evaluate_scene_a

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();assert not a.output.exists();rows=[]
    for case in [6,48,71,78,100]:
        raw,settings,waits=context(ROOT/f'数据/processed/q1/data/case_{case:03}.json')
        folder=ROOT/f'图表/runs/20260925-A-q1-timed-cold/case_{case:03}_5cores'
        paths=sorted(folder.glob('accepted_*/plan.json'))[-4:];plans=[json.loads(p.read_text(encoding='utf-8')) for p in paths]
        cached=TaskReuseEvaluator(raw,settings['bandwidth'],settings['capacity'],waits['task_cross_core_wait_cycles'],waits['task_same_core_wait_cycles'])
        t=time.monotonic();first=[evaluate_scene_a(raw,p,settings['bandwidth'],settings['capacity'],waits['task_cross_core_wait_cycles'],waits['task_same_core_wait_cycles']) for p in plans+plans];plain_seconds=time.monotonic()-t
        t=time.monotonic();second=[cached.evaluate(p) for p in plans+plans];cache_seconds=time.monotonic()-t
        assert first==second
        for path,r in zip(paths,second):
            with gzip.open(path.parent/'evaluation.json.gz','rt',encoding='utf-8') as f:saved=json.load(f)
            assert json.loads(json.dumps(r))==saved
        assert second[-1]==original(raw,settings,waits,plans[-1])
        rows.append(dict(case=case,candidates=len(first),all_fields_equal=True,plain_seconds=plain_seconds,cache_seconds=cache_seconds,reuse=cached.stats()))
    write_json(a.output,dict(role='Fixed saved candidate pool plus deliberate second pass; not search-quality evidence',rows=rows));print(json.dumps(rows),flush=True)

if __name__=='__main__':main()
