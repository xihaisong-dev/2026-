"""Independent original-official replay of a timed solver's selected checkpoint."""
import argparse,gzip,json,time
from pathlib import Path
from q1_io import PROCESSED,official,verify,sha,write_json

def main():
    p=argparse.ArgumentParser();p.add_argument('--runs',nargs='+',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    assert not a.output.exists();verify();mod=official()
    from evaluation_validation import read_evaluation_config
    config=PROCESSED/'data/config.txt';settings=read_evaluation_config(str(config));waits=mod.read_scene_a_config(str(config));rows=[]
    for folder in a.runs:
        run=json.loads((folder/'run.json').read_text(encoding='utf-8'));assert run['complete'] and run['within_limit'] and not run.get('worker_error')
        out=folder/run['selected']['folder'];plan=json.loads((out/'plan.json').read_text(encoding='utf-8'))
        exported=next(folder.glob('case_*_multicore_res.json'));case=exported.stem.split('_multicore')[0]
        raw=json.loads((PROCESSED/'data'/f'{case}.json').read_text(encoding='utf-8-sig'))
        assert json.loads(exported.read_text(encoding='utf-8'))==plan
        with gzip.open(out/'evaluation.json.gz','rt',encoding='utf-8') as f:saved=json.load(f)
        start=time.monotonic();fresh=mod.evaluate_scene_a(raw,plan,settings['bandwidth'],settings['capacity'],waits['task_cross_core_wait_cycles'],waits['task_same_core_wait_cycles'])
        assert json.loads(json.dumps(fresh))==saved
        rows.append(dict(run=str(folder),case=case,cores=fresh['num_cores'],full_official_replay_equal=True,makespan=fresh['makespan'],plan_sha256=sha(exported.read_bytes()),verification_seconds=time.monotonic()-start))
    write_json(a.output,dict(passed=True,count=len(rows),records=rows,timing_scope='Additional audit; not solver runtime'))
    print(json.dumps(rows,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
