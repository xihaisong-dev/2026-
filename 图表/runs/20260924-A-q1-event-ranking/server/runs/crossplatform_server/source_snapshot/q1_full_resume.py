"""Verified checkpoint reuse; never modify the source run."""
import json
from pathlib import Path
import shutil
from q1_io import sha,write_json


def verify_sources(summary):
    # Only orchestration/reporting may change when resuming. Solver source stays frozen.
    reporting={'q1_full_run.py','q1_full_resume.py','q1_full_profile.py',
               'q1_full_plot.py','q1_full_interpret.py','q1_graph_census.py'}
    for name,h in summary['code_sha256'].items():
        if name not in reporting and sha((Path(__file__).parent/name).read_bytes())!=h:
            raise ValueError('Cannot reuse results after solver change: '+name)


def restore(prior,out,fixed):
    if prior is None or not (prior/'row.json').exists():return None
    row=json.loads((prior/'row.json').read_text(encoding='utf-8'))
    if row['singlecore_makespan']!=fixed:raise ValueError('Changed denominator')
    for name,h in row['artifacts'].items():
        if sha((prior/name).read_bytes())!=h:raise ValueError('Checkpoint hash mismatch')
    shutil.copytree(prior,out)
    row['reused_solver_from']=str(prior);row['calls_this_attempt']=0
    write_json(out/'row.json',row)
    return row


def restore_cache(prior,out):
    if prior is not None and prior.is_dir():
        shutil.copytree(prior,out)
