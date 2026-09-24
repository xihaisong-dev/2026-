"""Tie-aware ranking diagnostics; each row belongs to one frozen candidate pool."""
import math


def ranks(values):
    out = [0.] * len(values)
    order = sorted(range(len(values)), key=values.__getitem__)
    i = 0
    while i < len(order):
        j = i + 1
        while j < len(order) and values[order[j]] == values[order[i]]:
            j += 1
        for k in order[i:j]:
            out[k] = (i + j - 1) / 2
        i = j
    return out


def metrics(rows, field):
    if not rows:
        return {'n': 0, 'spearman': None, 'top1_regret': None,
                'top2_regret': None, 'top2_covers_best': None}
    x, y = ranks([r[field] for r in rows]), ranks([r['official'] for r in rows])
    mx, my = sum(x)/len(x), sum(y)/len(y)
    den = math.sqrt(sum((v-mx)**2 for v in x)*sum((v-my)**2 for v in y))
    rho = sum((a-mx)*(b-my) for a,b in zip(x,y))/den if den else None
    ordered = sorted(rows, key=lambda r: (r[field], r['label']))
    best = min(r['official'] for r in rows)
    regret2 = min(r['official'] for r in ordered[:2])-best
    return {'n': len(rows), 'spearman': rho,
            'top1_regret': ordered[0]['official']-best,
            'top2_regret': regret2, 'top2_covers_best': regret2 == 0,
            'top2_labels': [r['label'] for r in ordered[:2]]}
