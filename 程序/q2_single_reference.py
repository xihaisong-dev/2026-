"""Recompute the prescribed single-core denominator using Q1's pinned exact engine.
This is NOT scene-A multicore score reuse and never evaluates scene-B candidates.
"""
from q1_fast_evaluator import evaluate_scene_a,BACKEND_ID


def fixed_reference_fast(raw,settings):
    from singlecore_evaluate import build_singlecore_plan
    result=evaluate_scene_a(raw,build_singlecore_plan(raw),settings['bandwidth'],settings['capacity'],0,0)
    result['execution_mode']='singlecore';result['input_plan']=None
    return result
