"""Conditional replay from saved anchor hashes; never a fresh benchmark claim."""
from collections import Counter
from q1_io import ROOT,write_json
from q2_full_campaign import OUT as SOURCE,read
from q2_route_diagnosis import best,OUT
from q2_reserve_gate import refill


def main():
    records=[];counts=Counter()
    for i in range(1,101):
        for k in range(2,6):
            l=read(SOURCE/f'cases/case_{i:03}/{k}/legacy/search.json')['evaluations']
            r=read(SOURCE/f'cases/case_{i:03}/{k}/routed/search.json')['evaluations']
            menu,n=refill(r[:2],r[2:8],l[6:8],lambda x:x['plan_sha256'])
            anchor=best(r[:2]+menu)
            origin=next((a for a,rr in [('routed',r),('legacy',l)] if best(rr[:8])['plan_sha256']==anchor['plan_sha256']),None)
            f=best(r[:2]+menu+(r[8:] if origin=='routed' else l[8:])) if origin else None
            records.append(dict(case=i,cores=k,admitted=n,anchor_source=origin,expected_makespan=f['makespan'] if f else None,expected_plan_sha256=f['plan_sha256'] if f else None))
            counts['unknown' if not f else 'win' if f['makespan']<best(r)['makespan'] else 'loss' if f['makespan']>best(r)['makespan'] else 'tie']+=1
    result=dict(status='posthoc_conditional_only',counts=dict(counts),records=records)
    p=OUT/'conditional_reserve.json'
    if p.exists():assert read(p)==result
    else:write_json(p,result)
    print(dict(counts))


if __name__=='__main__':main()
