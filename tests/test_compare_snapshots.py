from __future__ import annotations

import unittest

from scripts.compare_snapshots import compare_snapshots


def _snapshot(*, objective: float, variables: dict[str, object], iterations: int) -> dict:
    return {
        "schema_version": 1,
        "comparison_contract": {
            "integer_objective": "exact",
            "floating_objective_abs_tol": 1e-9,
            "floating_objective_rel_tol": 1e-9,
        },
        "cases": {
            "floating_case": {
                "semantic": {
                    "status_category": "feasible",
                    "feasible": True,
                    "replayed_feasible": True,
                    "dag_recheck_passed": True,
                    "objective": {"kind": "floating", "value": objective},
                    "replayed_objective": objective,
                },
                "diagnostic": {
                    "variable_values": variables,
                    "iterations": iterations,
                },
            }
        },
    }


def _integer_snapshot(value: int) -> dict:
    snapshot = _snapshot(objective=float(value), variables={"1": value}, iterations=1)
    semantic = snapshot["cases"]["floating_case"]["semantic"]
    semantic["objective"] = {"kind": "integer", "value": value}
    semantic["replayed_objective"] = value
    return snapshot


class CompareSnapshotsTest(unittest.TestCase):
    def test_semantic_comparison_ignores_equivalent_assignments_and_diagnostics(self) -> None:
        baseline = _snapshot(objective=1.0, variables={"1": 2}, iterations=10)
        candidate = _snapshot(objective=1.0 + 5e-10, variables={"1": 3}, iterations=12)

        self.assertEqual(compare_snapshots(baseline, candidate), [])

    def test_integer_objective_difference_fails(self) -> None:
        errors = compare_snapshots(_integer_snapshot(3), _integer_snapshot(4))

        self.assertIn("floating_case: integer objective differs: 3 != 4", errors)

    def test_invalid_native_replay_fails(self) -> None:
        baseline = _integer_snapshot(3)
        candidate = _integer_snapshot(3)
        candidate["cases"]["floating_case"]["semantic"]["dag_recheck_passed"] = False

        errors = compare_snapshots(baseline, candidate)

        self.assertIn("candidate floating_case: native replay did not pass DAG validation", errors)


if __name__ == "__main__":
    unittest.main()
