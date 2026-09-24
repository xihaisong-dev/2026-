"""Screen new routes with comparable fixed local profiles, not global outcomes."""
import math
import time
from q1_search_tools import replay


def compare_local_profiles(g, candidate_prediction, incumbent_plan, incumbent_result):
    start=time.perf_counter()
    durations={int(s):v['local_makespan'] for s,v in incumbent_result['step3_by_task'].items()}
    incumbent_prediction=replay(g,incumbent_plan,durations)
    if not math.isfinite(candidate_prediction) or not math.isfinite(incumbent_prediction):
        raise ValueError('Non-finite opportunity prediction')
    allowed=candidate_prediction < incumbent_prediction
    return allowed, dict(candidate_local=candidate_prediction,incumbent_local=incumbent_prediction,
                         predicted_gain=incumbent_prediction-candidate_prediction,
                         allowed=allowed,rule='strict local-profile gain; no tuned margin',
                         full_score_calls=0,local_preparation_calls=0,
                         seconds=time.perf_counter()-start)


def compare_event_profiles(raw, g, candidate_plan, incumbent_plan):
    """Fixed three-pass DDR proxy; local preparation costs are explicitly counted.

    Same candidate pool and ordering as local ranking. No global evaluation and
    no result-dependent fitted coefficients. Rebuild both prepared plans so the
    Pipe and memory dependency semantics are identical on both sides.
    """
    from q1_local_rank import LocalRank
    start=time.perf_counter();ranker=LocalRank(raw,g,event=True)
    candidate,_,_=ranker.score(candidate_plan)
    candidate_local=ranker.last_components['local']
    incumbent,_,_=ranker.score(incumbent_plan)
    incumbent_local=ranker.last_components['local']
    if not all(math.isfinite(x) for x in [candidate,incumbent]):
        raise ValueError('Non-finite event prediction')
    stats=ranker.stats()
    assert stats['global_evaluations']==0
    return candidate<incumbent,dict(candidate_event=candidate,incumbent_event=incumbent,
        candidate_local=candidate_local,incumbent_local=incumbent_local,
        predicted_gain=incumbent-candidate,allowed=candidate<incumbent,
        rule='strict fixed-three-pass dependency/DDR prediction gain',
        full_score_calls=0,local_preparation_calls=stats['calls'],preparation=stats,
        seconds=time.perf_counter()-start)
