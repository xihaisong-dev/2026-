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
