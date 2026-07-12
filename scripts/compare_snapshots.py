from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


def _compare_objective(
    case_name: str,
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    contract: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    if baseline.get("kind") != candidate.get("kind"):
        return [f"{case_name}: objective kind differs: {baseline.get('kind')} != {candidate.get('kind')}"]

    baseline_value = baseline.get("value")
    candidate_value = candidate.get("value")
    if baseline.get("kind") == "integer":
        if baseline_value != candidate_value:
            errors.append(f"{case_name}: integer objective differs: {baseline_value} != {candidate_value}")
        return errors

    abs_tol = float(contract["floating_objective_abs_tol"])
    rel_tol = float(contract["floating_objective_rel_tol"])
    if not math.isclose(float(baseline_value), float(candidate_value), abs_tol=abs_tol, rel_tol=rel_tol):
        errors.append(
            f"{case_name}: floating objective differs: {baseline_value} != {candidate_value} "
            f"(abs_tol={abs_tol}, rel_tol={rel_tol})"
        )
    return errors


def _validate_replay(case_name: str, semantic: dict[str, Any], contract: dict[str, Any]) -> list[str]:
    if not semantic.get("feasible"):
        return [f"{case_name}: solution is not feasible"]
    if not semantic.get("replayed_feasible"):
        return [f"{case_name}: replayed solution is not feasible"]
    if not semantic.get("dag_recheck_passed"):
        return [f"{case_name}: native replay did not pass DAG validation"]

    objective = semantic["objective"]
    replayed = semantic.get("replayed_objective")
    replay_objective = {"kind": objective["kind"], "value": replayed}
    return [
        error.replace(f"{case_name}: ", f"{case_name}: replayed ", 1)
        for error in _compare_objective(case_name, objective, replay_objective, contract)
    ]


def compare_snapshots(baseline: dict[str, Any], candidate: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if baseline.get("schema_version") != 1 or candidate.get("schema_version") != 1:
        return ["both snapshots must use schema_version 1"]
    if baseline.get("comparison_contract") != candidate.get("comparison_contract"):
        return ["snapshot comparison contracts differ"]

    contract = baseline["comparison_contract"]
    baseline_cases = baseline.get("cases", {})
    candidate_cases = candidate.get("cases", {})
    if set(baseline_cases) != set(candidate_cases):
        return [
            "snapshot case sets differ: "
            f"baseline={sorted(baseline_cases)}, candidate={sorted(candidate_cases)}"
        ]

    for case_name in sorted(baseline_cases):
        baseline_semantic = baseline_cases[case_name]["semantic"]
        candidate_semantic = candidate_cases[case_name]["semantic"]
        errors.extend(_validate_replay(f"baseline {case_name}", baseline_semantic, contract))
        errors.extend(_validate_replay(f"candidate {case_name}", candidate_semantic, contract))
        if baseline_semantic.get("status_category") != candidate_semantic.get("status_category"):
            errors.append(
                f"{case_name}: status category differs: "
                f"{baseline_semantic.get('status_category')} != {candidate_semantic.get('status_category')}"
            )
        errors.extend(
            _compare_objective(
                case_name,
                baseline_semantic["objective"],
                candidate_semantic["objective"],
                contract,
            )
        )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare OptAgent semantic regression snapshots")
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    candidate = json.loads(args.candidate.read_text(encoding="utf-8"))
    errors = compare_snapshots(baseline, candidate)
    report = {"passed": not errors, "errors": errors}
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
