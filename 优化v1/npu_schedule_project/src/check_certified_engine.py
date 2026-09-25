"""Small exact/fallback/fault checks for the optional certified scoring engine.

Faults are injected only into this test process. No official source, saved
experiment or input data is modified. Expected failures never become results.
"""
import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch
from evaluate import ROOT, read_json, write_json, evaluate_plan, evaluate_singlecore, flatten_result
from solver import generate_candidates
from certified_evaluate import evaluate_a_candidate, CERTIFICATE_VERSION
import run_certified


def prepare_baseline(folder, case):
    (folder/'baselines').mkdir(parents=True,exist_ok=True)
    source=ROOT/'results'/'baselines'
    if all((source/(case+s)).exists() for s in ('.json.gz','.meta.json')):
        for suffix in ('.json.gz','.meta.json'):shutil.copy2(source/(case+suffix),folder/'baselines'/(case+suffix))
    else:
        g=read_json(ROOT/'data'/(case+'.json'));r=evaluate_singlecore(g)
        write_json(folder/'baselines'/(case+'.json.gz'),r)
        write_json(folder/'baselines'/(case+'.meta.json'),flatten_result(r,case=case,baseline_makespan=r['makespan']))


def main():
    case='case_010';g=read_json(ROOT/'data'/(case+'.json'))
    plan=generate_candidates(g,3,1)[0][1]
    scored,metadata=evaluate_a_candidate(g,plan);actual=evaluate_plan(g,plan,1)
    assert metadata['certificate_passed'] and scored['scene']=='B'
    assert actual['makespan']==scored['makespan'] and actual['data_movement_bytes']==scored['data_movement_bytes']
    other=read_json(ROOT/'data/case_019.json')
    cut=next(p for n,p in generate_candidates(other,5,1) if n.startswith('window'))
    fallback,meta=evaluate_a_candidate(other,cut)
    assert not meta['certificate_passed'] and fallback['scene']=='A'
    with tempfile.TemporaryDirectory(prefix='certified_check_') as temp:
        root=Path(temp);pilot=root/'valid';prepare_baseline(pilot,case)
        rows=run_certified.selection_job(ROOT/'data'/(case+'.json'),pilot,3)
        r=read_json(pilot/rows[0]['official_result_path']);plan=read_json(pilot/rows[0]['plan_path'])
        assert r==json.loads(json.dumps(evaluate_plan(g,plan,1))) and r['scene']=='A'
        assert rows[0]['score_source']=='certified_official_B' and rows[0]['final_verification_seconds']>0
        assert abs(rows[0]['total_evaluation_seconds']-rows[0]['search_evaluation_seconds']-rows[0]['final_verification_seconds'])<1e-9
        negative=root/'negative';prepare_baseline(negative,case)
        original=run_certified.evaluate_plan
        def inject_final_fault(graph,plan,problem,config=None):
            value=original(graph,plan,problem,config)
            if problem==1:value['makespan']+=1
            return value
        raised=False
        with patch('run_certified.evaluate_plan',side_effect=inject_final_fault):
            try:run_certified.selection_job(ROOT/'data'/(case+'.json'),negative,3)
            except AssertionError:raised=True
        assert raised and not (negative/'records'/f'{case}_n3.json').exists()
        raised=False
        with patch('run_certified.evaluate_a_candidate',side_effect=AssertionError('Intentional test-only certificate invariant failure')):
            try:run_certified.selection_job(ROOT/'data'/(case+'.json'),negative,3)
            except AssertionError:raised=True
        assert raised and not (negative/'records'/f'{case}_n3.json').exists()
    print('PASS:',CERTIFICATE_VERSION,'eligible scores, ineligible fallback, genuine final A, timing, and both fault guards')

if __name__=='__main__':main()
