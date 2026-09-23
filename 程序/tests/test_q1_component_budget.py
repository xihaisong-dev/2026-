import unittest
from unittest.mock import patch
from test_q1 import fixture, SETTINGS, WAITS
from q1_solver import Graph, validate
from q1_structural_seeds import guarded_component_candidate
from q1_experimental import solve_experimental, CostGraph
from q1_ablation import CONFIGS


class ComponentBudgetTests(unittest.TestCase):
    def test_gate_uses_structure_and_capacity_not_case_name(self):
        chain = fixture([(i, i+1) for i in range(8)])
        plans, info = guarded_component_candidate(chain, SETTINGS, WAITS, 3)
        self.assertEqual(plans, [])
        self.assertEqual(info['gate'], 'insufficient_independent_components')
        independent = fixture([(u, u+20) for u in range(12)])
        plans, info = guarded_component_candidate(independent, SETTINGS, WAITS, 3)
        self.assertEqual(len(plans), 1)
        self.assertEqual(info['gate'], 'eligible')
        validate(Graph(independent, SETTINGS, WAITS), plans[0][1])
        tiny = dict(SETTINGS, capacity={'L1': 1, 'UB': 1})
        plans, info = guarded_component_candidate(independent, tiny, WAITS, 3)
        self.assertEqual(plans, [])
        self.assertEqual(info['gate'], 'all_components_have_large_union_footprint')

    def test_dominant_component_routes_to_original_search(self):
        raw = fixture([(i, i+1) for i in range(8)] + [(20,21),(30,31)])
        plans, info = guarded_component_candidate(raw, SETTINGS, WAITS, 3)
        self.assertEqual(plans, [])
        self.assertEqual(info['gate'], 'dominant_component')
        base = solve_experimental(raw, SETTINGS, WAITS, 3, 12, 4, CONFIGS['shared_region'])
        for name in ['component_guard', 'component_slot', 'component_followup']:
            result = solve_experimental(raw, SETTINGS, WAITS, 3, 12, 4, CONFIGS[name])
            self.assertEqual(result[0], base[0])
            self.assertEqual([(x['candidate'],x['makespan']) for x in result[2]['evaluations']],
                             [(x['candidate'],x['makespan']) for x in base[2]['evaluations']])

    def test_one_probe_budget_and_slot_replaces_only_random(self):
        raw = fixture([(u,u+30) for u in range(30)])
        for name in ['component_guard','component_slot']:
            _, result, stats = solve_experimental(raw, SETTINGS, WAITS, 3, 12, 0, CONFIGS[name])
            self.assertEqual(len(stats['evaluations']),12)
            self.assertEqual(stats['protected_grain_attempts'],[.5,1.,2.,.25])
            self.assertLessEqual(stats['structural_seed_stats']['evaluated'],1)
            self.assertEqual(result['makespan'],min(x['makespan'] for x in stats['evaluations']))
            if name=='component_slot':
                for record in stats['structural_seed_stats']['ledger']:
                    self.assertTrue(record['replaces_candidate'].startswith('random_'))

    def test_losing_probe_does_not_update_observations(self):
        raw=fixture([(u,u+30) for u in range(30)])
        # A legal single-core packing is deliberately poor but uniquely labelled.
        poor={'node_to_subgraph':{str(o['id']):99 for o in raw['ops']},'core_schedules':[[99],[],[]]}
        # Put one independent component on another core to avoid fallback dedup.
        for u in [0,30]: poor['node_to_subgraph'][str(u)]=100
        poor['core_schedules'][1]=[100]
        info=dict(selected_compute_lower_bound=0,gate='test_fixture')
        observed=[]
        original=CostGraph.observe
        def record(self,plan,result):
            observed.append(plan)
            return original(self,plan,result)
        with patch('q1_structural_seeds.guarded_component_candidate',return_value=([('forced_poor',poor)],info)), patch.object(CostGraph,'observe',record):
            _,_,stats=solve_experimental(raw,SETTINGS,WAITS,3,12,0,CONFIGS['component_slot'])
        probe=next(x for x in stats['proposal_ledger'] if x['candidate']=='structural_forced_poor')
        self.assertEqual(probe['status'],'evaluated')
        self.assertFalse(probe['cost_observation_applied'])
        self.assertNotIn(poor,observed)

    def test_followup_is_diverse_and_keeps_first_candidate(self):
        raw = fixture([(u,u+30) for u in range(30)])
        for i, op in enumerate(raw['ops']):
            op['cycles'] = (i*37)%91+10
        one, _ = guarded_component_candidate(raw, SETTINGS, WAITS, 3)
        two, _ = guarded_component_candidate(raw, SETTINGS, WAITS, 3, max_candidates=2)
        self.assertEqual(one[0], two[0])
        self.assertEqual(len(two), 2)
        def groups(plan):
            ids = set(plan['node_to_subgraph'].values())
            return {frozenset(u for u,s in plan['node_to_subgraph'].items() if s==sid) for sid in ids}
        self.assertNotEqual(groups(two[0][1]), groups(two[1][1]))
        for _, plan in two:
            validate(Graph(raw, SETTINGS, WAITS), plan)

    def test_followup_unlock_reclaims_only_duplicate_or_random(self):
        raw = fixture([(u,u+30) for u in range(30)])
        for i, op in enumerate(raw['ops']): op['cycles'] = (i*37)%91+10
        plans, info = guarded_component_candidate(raw, SETTINGS, WAITS, 3, max_candidates=2)
        # Disable valid lower-bound pruning to exercise the second scoring path.
        info['candidate_compute_bounds'] = {kind: 0 for kind, _ in plans}
        with patch('q1_structural_seeds.guarded_component_candidate', return_value=(plans,info)):
            _, result, stats = solve_experimental(raw, SETTINGS, WAITS, 3, 12, 0, CONFIGS['component_followup'])
        routing = stats['structural_seed_stats']
        self.assertTrue(routing['followup_unlocked'])
        self.assertEqual(routing['evaluated'], 2)
        self.assertEqual(len(stats['evaluations']), 12)
        self.assertEqual(stats['protected_grain_attempts'], [.5,1.,2.,.25])
        second = routing['ledger'][1]
        self.assertEqual(second['opportunity'], 'equivalent_duplicate')
        self.assertLess(second['replaced_equivalent_evaluation_id'], second['evaluation_id'])
        self.assertEqual(result['makespan'], min(x['makespan'] for x in stats['evaluations']))

    def test_no_followup_after_non_improving_first_probe(self):
        raw = fixture([(u,u+30) for u in range(30)])
        plans, _ = guarded_component_candidate(raw, SETTINGS, WAITS, 3)
        poor = {'node_to_subgraph':{str(o['id']):99 for o in raw['ops']}, 'core_schedules':[[99],[100],[]]}
        for u in [0,30]: poor['node_to_subgraph'][str(u)] = 100
        info = dict(selected_compute_lower_bound=0, gate='test', candidate_compute_bounds={})
        with patch('q1_structural_seeds.guarded_component_candidate',return_value=([('poor',poor),('unused',plans[0][1])],info)):
            _,_,stats = solve_experimental(raw, SETTINGS, WAITS, 3, 12, 0, CONFIGS['component_followup'])
        self.assertFalse(stats['structural_seed_stats']['followup_unlocked'])
        self.assertEqual(len(stats['structural_seed_stats']['ledger']), 1)
        self.assertFalse(any(x['candidate']=='structural_unused' for x in stats['evaluations']))

    def test_local_rank_is_local_only_and_keeps_budget(self):
        raw = fixture([(u,u+30) for u in range(30)])
        for i, op in enumerate(raw['ops']): op['cycles'] = (i*37)%91+10
        _, info = guarded_component_candidate(raw, SETTINGS, WAITS, 3, max_candidates=2, ranking='local')
        self.assertEqual(info['local_preparation']['global_evaluations'], 0)
        self.assertLessEqual(info['local_preparation']['calls'], 3)
        self.assertEqual([x['local_prediction'] for x in info['ranked']], sorted(x['local_prediction'] for x in info['ranked']))
        _, result, stats = solve_experimental(raw, SETTINGS, WAITS, 3, 12, 0, CONFIGS['component_local_rank'])
        self.assertEqual(len(stats['evaluations']), 12)
        self.assertEqual(stats['protected_grain_attempts'], [.5,1.,2.,.25])
        self.assertLessEqual(stats['structural_seed_stats']['evaluated'], 2)
        self.assertEqual(result['makespan'], min(x['makespan'] for x in stats['evaluations']))

    def test_proposal_observer_cannot_modify_search(self):
        raw = fixture([(u,u+15) for u in range(15)])
        base = solve_experimental(raw,SETTINGS,WAITS,3,12,0,CONFIGS['component_followup'])
        def observer(plan, label): plan['node_to_subgraph'].clear()
        actual = solve_experimental(raw,SETTINGS,WAITS,3,12,0,CONFIGS['component_followup'],on_proposal=observer)
        self.assertEqual(base[0], actual[0])
        self.assertEqual(base[1], actual[1])

    def test_incompatible_features_rejected(self):
        with self.assertRaisesRegex(ValueError, 'requires component_slot'):
            solve_experimental(fixture([(0,1)]), SETTINGS, WAITS, 2, 12, 0, CONFIGS['component_guard']+['component_followup'])
        with self.assertRaisesRegex(ValueError,'Component routing'):
            solve_experimental(fixture([(0,1)]),SETTINGS,WAITS,2,12,0,CONFIGS['seed_combined']+['component_slot'])


if __name__=='__main__':unittest.main()
