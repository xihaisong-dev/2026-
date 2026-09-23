"""Conservative structural bounds, never an assertion that the bound is attainable."""
from collections import defaultdict
import math


def structural_bound(g, cores):
    if cores < 1:
        raise ValueError('cores must be positive')
    loads = defaultdict(int)
    for op in g.ops.values():
        loads[op['pipe']] += op['cycles']
    pipe_bounds = {p: math.ceil(v / cores) for p, v in loads.items()}
    # Original COPY_IN/OUT are excluded: their generated task copies can differ.
    # Contracted compute precedence and all non-copy execution cycles remain mandatory.
    critical = max(g.rank.values(), default=0)
    bound = max([critical, *pipe_bounds.values()])
    return {'lower_bound_cycles': bound, 'compute_critical_path_cycles': critical,
            'noncopy_pipe_cycles': dict(sorted(loads.items())),
            'pipe_load_lower_bounds': dict(sorted(pipe_bounds.items())),
            'attainability_proven': False,
            'scope': 'mandatory non-copy pipe work and contracted compute precedence only; '
                     'omits boundary copies, extra waits, spill and DDR contention'}
