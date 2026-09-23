import unittest
from test_q1 import fixture, SETTINGS, WAITS, evaluate
from q1_experimental import CostGraph, solve_experimental
from q1_local_rank import LocalRank
from q1_rank_metrics import metrics


class RankingTests(unittest.TestCase):
    def test_ties_and_top_two(self):
        rows = [{'label': str(i), 'p': p, 'official': t}
                for i,(p,t) in enumerate([(1,3),(1,1),(2,2)])]
        r = metrics(rows, 'p')
        self.assertEqual(r['spearman'], 0)
        self.assertEqual(r['top1_regret'], 2)
        self.assertTrue(r['top2_covers_best'])
        self.assertIsNone(metrics(rows[:1], 'p')['spearman'])

    def test_preparation_matches_official_without_global_call(self):
        raw = fixture([(0,1),(1,2),(0,3)])
        plan = {'node_to_subgraph': {str(u): u for u in range(4)},
                'core_schedules': [[0,1,2],[3]]}
        g = CostGraph(raw, SETTINGS, WAITS, True)
        ranker = LocalRank(raw,g)
        _, duration, traffic = ranker.score(plan)
        self.assertEqual(ranker.stats()['global_evaluations'], 0)
        actual = evaluate(raw, plan)
        self.assertEqual(duration, {int(s):v['local_makespan'] for s,v in actual['step3_by_task'].items()})
        self.assertEqual(traffic, actual['data_movement_bytes'])
        ranker.score(plan)
        self.assertEqual(ranker.stats()['partition_hits'], 1)

    def test_duplicate_grains_have_evidence(self):
        raw = fixture([(u,u+8) for u in range(8)])
        _, _, stats = solve_experimental(raw, SETTINGS, WAITS, 2, 12, 0,
                ['local_cost','critical','insertion','comm_rank','partition_guard'])
        self.assertEqual(len(stats['protected_grain_ledger']), 4)
        self.assertTrue(any(r['status']=='duplicate' for r in stats['protected_grain_ledger']))
        for r in stats['protected_grain_ledger']:
            self.assertIn(r['status'], ['evaluated','duplicate','infeasible'])
            if r['status']=='duplicate':
                evidence = [e for e in stats['proposal_ledger'] if e['status']=='evaluated'
                            and e['evaluation_id']==r['evaluation_id']]
                self.assertEqual(evidence[0]['plan_sha256'], r['plan_sha256'])

    def test_bounded_regions_and_budget(self):
        from q1_ranked_region import ranked_candidates, structure
        from q1_solver import validate
        raw = fixture([(u,u+1) for u in range(14)])
        g = CostGraph(raw, SETTINGS, WAITS, True)
        plan = g.schedule({u:u for u in g.ops}, 3)[0]
        result = evaluate(raw,plan)
        for wide,uphill in [(False,False),(True,False),(False,True)]:
            proposals = list(ranked_candidates(g,raw,plan,result,3,wide,uphill))
            info = g.boundary_stats[-1]
            self.assertLessEqual(info['probes'],24)
            self.assertLessEqual(len(info['walk_scores']),6)
            self.assertTrue(all(len(r)<=12 for r in info['regions']))
            self.assertEqual(info['preparation']['global_evaluations'],0)
            self.assertLessEqual(len(proposals),2)
            for _,trial in proposals:
                validate(g,trial)
                self.assertGreater(evaluate(raw,trial)['makespan'],0)
        for extra in [[],['wide_region'],['uphill_region']]:
            _,result,stats=solve_experimental(raw,SETTINGS,WAITS,3,12,0,
                ['local_cost','critical','insertion','comm_rank','partition_guard','region','exact_region']+extra)
            self.assertEqual(stats['official_calls'],12)
            self.assertEqual(result['makespan'],min(r['makespan'] for r in stats['evaluations']))
