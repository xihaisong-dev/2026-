"""Causal control: same exploration/RNG, discard gains ONLY at selection."""
import argparse,json
from collections import Counter
from unittest.mock import patch
import q23_reward_prefix as target
from q23_cache_search import run as supervised_run

original_choose=target.choose

def prior_only(index,prefix,cycle,counts,gains,rng):
    return original_choose(index,prefix,cycle,counts,Counter(),rng)

def worker(args,deadline):
    with patch.object(target,'choose',prior_only):target.worker(args,deadline)

def run(args):
    import q23_cache_search
    with patch.object(q23_cache_search,'worker',worker):return supervised_run(args)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--graph',required=True);p.add_argument('--seed-plan',required=True);p.add_argument('--anchor',required=True);p.add_argument('--output',required=True)
    a=vars(p.parse_args());a.update(problem=3,policy='reward',ordering_prepare=False,reuse=True,cache_mib=32,seconds=590,cores=5,seed=0,max_proposals=384,ablation='prior_only_selection')
    print(json.dumps(run(a)))
