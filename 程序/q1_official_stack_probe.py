"""Bounded stack sampling of a known slow original evaluation (not validation)."""
import argparse
import faulthandler
import json
import subprocess
import sys
import time
from pathlib import Path
from q1_io import ROOT, PROCESSED, official, write_json


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--child',action='store_true')
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.child:
        mod=official()
        from evaluation_validation import read_evaluation_config
        raw=json.loads((PROCESSED/'data/case_014.json').read_text('utf-8-sig'))
        plan=json.loads((ROOT/'图表/runs/20260924-A-q1-delivery-r02/solutions/5cores/case_014_multicore_res.json').read_text('utf-8'))
        settings=read_evaluation_config(str(PROCESSED/'data/config.txt'))
        waits=mod.read_scene_a_config(str(PROCESSED/'data/config.txt'))
        faulthandler.dump_traceback_later(4,repeat=True)
        started=time.perf_counter()
        mod.evaluate_scene_a(raw,plan,settings['bandwidth'],settings['capacity'],
            waits['task_cross_core_wait_cycles'],waits['task_same_core_wait_cycles'])
        faulthandler.cancel_dump_traceback_later()
        print('Completed',time.perf_counter()-started,flush=True)
        return
    a.output.mkdir(parents=True,exist_ok=False)
    with (a.output/'stacks.log').open('wb') as f:
        t=time.monotonic();proc=subprocess.Popen([sys.executable,__file__,'--child','--output',str(a.output)],stdout=f,stderr=f)
        timeout=False
        try:proc.wait(timeout=26)
        except subprocess.TimeoutExpired:
            timeout=True;proc.kill();proc.wait()
    write_json(a.output/'probe.json',dict(case=14,cores=5,elapsed=time.monotonic()-t,
        sample_interval_seconds=4,intentional_probe_limit_seconds=26,
        terminated_by_probe_limit=timeout,returncode=proc.returncode,
        scope='partial original evaluator stack sampling; not a full validation or a solver timeout'))


if __name__=='__main__':main()
