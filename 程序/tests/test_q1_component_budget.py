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
        for name in ['component_guard', 'component_slot']:
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

    def test_incompatible_features_rejected(self):
        with self.assertRaisesRegex(ValueError,'Component routing'):
            solve_experimental(fixture([(0,1)]),SETTINGS,WAITS,2,12,0,CONFIGS['seed_combined']+['component_slot'])


if __name__=='__main__':unittest.main()
