"""Reuse a verified official whole-graph single-Task result on idle-padded cores.

This is result reuse, not a new evaluation. The search opportunity still counts.
All nonempty execution remains on core zero; empty cores cannot issue DDR work.
"""
import copy
import hashlib
import json


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def reference(raw,settings,waits,result):
    if result['num_cores']!=1 or len(result['per_core_timeline'])!=1:
        raise ValueError('Need an official single-core result')
    return {'context':digest([raw,settings,waits]),'result_sha256':digest(result),'result':result}


def reuse(record,raw,settings,waits,cores):
    if cores<1 or record['context']!=digest([raw,settings,waits]):
        raise ValueError('Single reference context mismatch')
    if record['result_sha256']!=digest(record['result']):
        raise ValueError('Single reference integrity failure')
    result=copy.deepcopy(record['result'])
    result.pop('execution_mode',None);result.pop('input_plan',None)
    result['num_cores']=cores
    result['memory_peak_by_core']={int(c):v for c,v in result['memory_peak_by_core'].items()}
    for c in range(1,cores):
        result['per_core_timeline'].append({'core_id':c,'tasks':[],'subgraphs':[],'ops':[]})
        result['memory_peak_by_core'][c]={p:0 for p in settings['capacity']}
    return result
