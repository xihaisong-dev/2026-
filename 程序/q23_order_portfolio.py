"""Compare ordering preparation with generation reuse enabled in both arms."""
import argparse,json
from unittest.mock import patch
from q23_order_prepare import OrderingPreparation
from q23_portfolio_reuse import worker as portfolio_worker
from q23_cache_search import run as supervised_run

def worker(args,deadline):
    import q23_selective_reuse
    if args.get('ordering_prepare'):
        with patch.object(q23_selective_reuse,'GenerationReuse',OrderingPreparation):
            portfolio_worker(args,deadline)
    else:portfolio_worker(args,deadline)

def run(args):
    import q23_cache_search
    with patch.object(q23_cache_search,'worker',worker):return supervised_run(args)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--problem',type=int,required=True,choices=[2,3]);p.add_argument('--graph',required=True);p.add_argument('--output',required=True)
    p.add_argument('--migration');p.add_argument('--seed-plan');p.add_argument('--anchor');p.add_argument('--ordering-prepare',action='store_true')
    p.add_argument('--seconds',type=float,default=590);p.add_argument('--cores',type=int,default=5);p.add_argument('--seed',type=int,default=0);p.add_argument('--max-proposals',type=int,default=96)
    a=vars(p.parse_args());a.update(cache_mib=32,reuse=True)
    print(json.dumps(run(a)))
