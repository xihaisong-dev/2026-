"""Execution-only addendum: exact fixed-reference acceleration, identical B search."""
import argparse,json
from pathlib import Path
import q2_main_campaign as campaign
from q2_single_reference import fixed_reference_fast,BACKEND_ID
from q1_io import sha


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['validation','scale']);p.add_argument('--case',type=int,required=True);a=p.parse_args()
    addendum=json.loads((campaign.OUT/'reference_backend_addendum.json').read_text(encoding='utf-8'))
    assert addendum['backend']==BACKEND_ID
    for name,h in addendum['sources'].items():assert sha(Path(__file__).with_name(name).read_bytes())==h
    campaign.fixed_reference=fixed_reference_fast
    campaign.run(a.phase,a.case)
