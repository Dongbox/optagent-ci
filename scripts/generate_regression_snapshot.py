from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
import json
from pathlib import Path
from typing import Any

from optagent import OptModel


SnapshotBuilder = Callable[[], OptModel]


def _build_integer_linear() -> OptModel:
    model = OptModel("integer-linear")
    x = model.int(0, 10, default=2, name="x")
    y = model.int(0, 10, default=3, name="y")
    model.constraint(x + y >= 7, "demand")
    model.minimize(x + y, "cost")
    return model


def _build_integer_scalar() -> OptModel:
    model = OptModel("integer-scalar")
    x = model.int(-5, 5, default=0, name="x")
    model.minimize((x - 2) * (x - 2), "distance")
    return model


def _build_floating_scalar() -> OptModel:
    model = OptModel("floating-scalar")
    x = model.int(0, 4, default=0, name="x")
    model.minimize(((x - 2) * (x - 2) * 0.5) + 0.25, "floating_distance")
    return model


CASES: dict[str, SnapshotBuilder] = {
    "integer_linear": _build_integer_linear,
    "integer_scalar": _build_integer_scalar,
    "floating_scalar": _build_floating_scalar,
}


def _objective_payload(value: Any) -> dict[str, Any]:
    if isinstance(value, int) and not isinstance(value, bool):
        return {"kind": "integer", "value": value}
    return {"kind": "floating", "value": float(value)}


def run_case(name: str) -> dict[str, Any]:
    model = CASES[name]()
    solution = model.solve(time_limit_s=0.2, log_level="off")
    constraints = [bool(row["expression"].value) for row in model.constraints]
    objectives = [row["expression"].value for row in model.objectives]
    decision_values = {
        str(row["expression"].id): row["expression"].value for row in model.decisions
    }
    objective = solution.objectives[0]
    return {
        "semantic": {
            "status_category": solution.status,
            "feasible": solution.feasible,
            "rechecked_feasible": all(constraints),
            "expression_recheck_passed": tuple(objectives) == solution.objectives,
            "objective": _objective_payload(objective),
            "rechecked_objective": objectives[0],
        },
        "diagnostic": {
            "solver_name": solution.solver_name,
            "decision_values": decision_values,
            "constraints": constraints,
        },
    }


def build_snapshot(*, case_names: Sequence[str] | None = None) -> dict[str, Any]:
    selected = list(case_names or CASES)
    unknown = sorted(set(selected) - CASES.keys())
    if unknown:
        raise ValueError(f"unknown regression snapshot cases: {', '.join(unknown)}")
    return {
        "schema_version": 2,
        "comparison_contract": {
            "integer_objective": "exact",
            "floating_objective_abs_tol": 1e-9,
            "floating_objective_rel_tol": 1e-9,
        },
        "cases": {name: run_case(name) for name in selected},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate OptAgent semantic regression snapshots")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case", action="append", dest="cases")
    args = parser.parse_args()
    snapshot = build_snapshot(case_names=args.cases)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
