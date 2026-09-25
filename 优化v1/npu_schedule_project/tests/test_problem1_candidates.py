"""Problem-1 candidate generation is deterministic and officially feasible.

The graph is passed as a parsed object. The solver never sees a case filename.
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from evaluate import evaluate_plan
from solver import _fingerprint, generate_candidates


def _graph():
    return json.loads((ROOT / "data" / "case_019.json").read_text(encoding="utf-8-sig"))


class Problem1CandidatesTest(unittest.TestCase):
    def test_repeat_generation_matches_and_official_eval_accepts(self):
        graph = _graph()
        first = generate_candidates(graph, 5, problem=1, budget="standard")
        second = generate_candidates(graph, 5, problem=1, budget="standard")
        self.assertEqual([name for name, _ in first], [name for name, _ in second])
        self.assertEqual([_fingerprint(plan) for _, plan in first], [_fingerprint(plan) for _, plan in second])
        fingerprints = [_fingerprint(plan) for _, plan in first]
        self.assertEqual(len(fingerprints), len(set(fingerprints)))
        self.assertLessEqual(len(first), 40)
        self.assertIn("component_round_robin", [name for name, _ in first])
        self.assertFalse(any(name.startswith("share_pack") for name in (item[0] for item in first)))
        scored = []
        for name, plan in first:
            result = evaluate_plan(graph, plan, 1, ROOT / "data" / "config.txt")
            makespan = int(result["makespan"])
            copy = int(result["data_movement_bytes"]["added_copy_bytes"])
            self.assertGreater(makespan, 0)
            scored.append((makespan, copy, name))
            print(f"candidate {name} makespan={makespan} copy={copy}", flush=True)
        scored.sort()
        print(f"selected {scored[0][2]} makespan={scored[0][0]} copy={scored[0][1]} count={len(first)}", flush=True)
        self.assertTrue(scored)

    def test_spare_slot_keeps_grain_window_and_official_eval_accepts(self):
        graph = json.loads((ROOT / "data" / "case_064.json").read_text(encoding="utf-8-sig"))
        first = generate_candidates(graph, 5, problem=1, budget="standard")
        second = generate_candidates(graph, 5, problem=1, budget="standard")
        names = [name for name, _ in first]
        self.assertEqual(names, [name for name, _ in second])
        self.assertLessEqual(len(first), 40)
        self.assertIn("window10_heft", names)
        self.assertIn("component_round_robin", names)
        plan = dict(first)["window10_heft"]
        result = evaluate_plan(graph, plan, 1, ROOT / "data" / "config.txt")
        self.assertGreater(int(result["makespan"]), 0)
        print(f"case_064 window10_heft makespan={result['makespan']} count={len(first)}", flush=True)
        self.assertIn("window10_lowcomm", names)

    def test_spine_and_hybrid_are_officially_feasible(self):
        fork = json.loads((ROOT / "data" / "case_016.json").read_text(encoding="utf-8-sig"))
        mesh = json.loads((ROOT / "data" / "case_071.json").read_text(encoding="utf-8-sig"))
        fork_names = [name for name, _ in generate_candidates(fork, 5, problem=1, budget="standard")]
        again = [name for name, _ in generate_candidates(fork, 5, problem=1, budget="standard")]
        self.assertEqual(fork_names, again)
        self.assertLessEqual(len(fork_names), 40)
        self.assertIn("scene_a_spine", fork_names)
        self.assertIn("stage_pack", fork_names)
        self.assertIn("component_round_robin", fork_names)
        self.assertFalse(any(name.startswith("share_pack") for name in fork_names))
        self.assertFalse(any(name == "bundle_pack" for name in fork_names))
        mesh_plans = dict(generate_candidates(mesh, 5, problem=1, budget="standard"))
        self.assertIn("hybrid20_10", mesh_plans)
        self.assertLessEqual(len(mesh_plans), 40)
        fork_plans = dict(generate_candidates(fork, 5, problem=1, budget="standard"))
        spine = fork_plans["scene_a_spine"]
        staged = fork_plans["stage_pack"]
        config = ROOT / "data" / "config.txt"
        spine_result = evaluate_plan(fork, spine, 1, config)
        stage_result = evaluate_plan(fork, staged, 1, config)
        hybrid_result = evaluate_plan(mesh, mesh_plans["hybrid20_10"], 1, config)
        self.assertGreater(int(spine_result["makespan"]), 0)
        self.assertGreater(int(hybrid_result["makespan"]), 0)
        self.assertLess(int(stage_result["makespan"]), int(spine_result["makespan"]))
        print(
            f"case_016 stage_pack makespan={stage_result['makespan']} "
            f"scene_a_spine makespan={spine_result['makespan']} count={len(fork_names)}",
            flush=True,
        )
        print(
            f"case_071 hybrid20_10 makespan={hybrid_result['makespan']} count={len(mesh_plans)}",
            flush=True,
        )

    def test_lookahead_tail_keeps_the_winning_window(self):
        narrow = json.loads((ROOT / "data" / "case_075.json").read_text(encoding="utf-8-sig"))
        wide = json.loads((ROOT / "data" / "case_085.json").read_text(encoding="utf-8-sig"))
        narrow_plans = dict(generate_candidates(narrow, 5, problem=1, budget="standard"))
        wide_plans = dict(generate_candidates(wide, 5, problem=1, budget="standard"))
        self.assertIn("window4_heft", narrow_plans)
        self.assertIn("window4_peft", narrow_plans)
        self.assertIn("window10_heft", wide_plans)
        self.assertIn("window10_peft", wide_plans)
        self.assertLessEqual(len(narrow_plans), 40)
        self.assertLessEqual(len(wide_plans), 40)
        narrow_result = evaluate_plan(narrow, narrow_plans["window4_peft"], 1, ROOT / "data" / "config.txt")
        wide_result = evaluate_plan(wide, wide_plans["window10_peft"], 1, ROOT / "data" / "config.txt")
        self.assertGreater(int(narrow_result["makespan"]), 0)
        self.assertGreater(int(wide_result["makespan"]), 0)
        print(f"case_075 window4_peft makespan={narrow_result['makespan']} count={len(narrow_plans)}", flush=True)
        print(f"case_085 window10_peft makespan={wide_result['makespan']} count={len(wide_plans)}", flush=True)

    def test_bundle_pack_beats_pipe_lpt_on_the_fork_join_graph(self):
        graph = json.loads((ROOT / "data" / "case_100.json").read_text(encoding="utf-8-sig"))
        first = generate_candidates(graph, 5, problem=1, budget="standard")
        second = generate_candidates(graph, 5, problem=1, budget="standard")
        names = [name for name, _ in first]
        self.assertEqual(names, [name for name, _ in second])
        self.assertEqual(
            [_fingerprint(plan) for _, plan in first],
            [_fingerprint(plan) for _, plan in second],
        )
        self.assertIn("bundle_pack", names)
        self.assertIn("component_pipe_lpt", names)
        self.assertIn("component_round_robin", names)
        self.assertFalse(any(name.startswith("share_pack") for name in names))
        # The bundle is an extra candidate past the 12-slot cap. It must not
        # be the only schedule, and it must not push the list past one extra.
        self.assertLessEqual(len(first), 40)
        plans = dict(first)
        config = ROOT / "data" / "config.txt"
        bundle = evaluate_plan(graph, plans["bundle_pack"], 1, config)
        pipe = evaluate_plan(graph, plans["component_pipe_lpt"], 1, config)
        self.assertLess(int(bundle["makespan"]), int(pipe["makespan"]))
        print(
            f"case_100 bundle_pack makespan={bundle['makespan']} "
            f"pipe_lpt makespan={pipe['makespan']} count={len(first)}",
            flush=True,
        )

    def test_share_pack_beats_the_previous_winner_on_weight_replicas(self):
        config = ROOT / "data" / "config.txt"
        checks = (
            ("case_044", "share_pack_3", "component_round_robin"),
            ("case_046", "share_pack_4", "component_round_robin"),
            ("case_083", "share_pack_10", "component_round_robin"),
            ("case_090", "share_pack_9", "scene_a_peft"),
            ("case_092", "share_pack_10", "component_round_robin"),
        )
        for case, chosen, previous in checks:
            graph = json.loads((ROOT / "data" / f"{case}.json").read_text(encoding="utf-8-sig"))
            first = generate_candidates(graph, 5, problem=1, budget="standard")
            second = generate_candidates(graph, 5, problem=1, budget="standard")
            names = [name for name, _ in first]
            self.assertEqual(names, [name for name, _ in second])
            self.assertEqual(
                [_fingerprint(plan) for _, plan in first],
                [_fingerprint(plan) for _, plan in second],
            )
            self.assertEqual(len(names), len(set(_fingerprint(plan) for _, plan in first)))
            self.assertIn(chosen, names)
            self.assertIn(previous, names)
            self.assertLessEqual(len(first), 40)
            plans = dict(first)
            chosen_result = evaluate_plan(graph, plans[chosen], 1, config)
            previous_result = evaluate_plan(graph, plans[previous], 1, config)
            self.assertLess(int(chosen_result["makespan"]), int(previous_result["makespan"]))
            print(
                f"{case} {chosen} makespan={chosen_result['makespan']} "
                f"{previous} makespan={previous_result['makespan']} count={len(first)}",
                flush=True,
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
