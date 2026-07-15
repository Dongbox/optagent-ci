from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time
from typing import Any, Sequence


TIER_BUDGETS = {"smoke": 2.0, "calibration": 5.0, "full": 10.0, "pressure": 30.0}
EXACT_BUDGETS = {"smoke": 10.0, "calibration": 20.0, "full": 30.0, "pressure": 30.0}


def verify_data_manifest(*, benchmark_root: Path, manifest_path: Path) -> list[str]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    case_root = benchmark_root / "benchmarks" / "cases"
    errors = []
    for item in payload.get("files", []):
        path = case_root / item["path"]
        if not path.is_file():
            errors.append(f"missing benchmark data file: {item['path']}")
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != item["sha256"]:
            errors.append(f"benchmark data checksum mismatch: {item['path']}")
    return errors


def _budget(case: dict[str, Any]) -> float:
    budgets = EXACT_BUDGETS if case["family"] == "exact_linear_mip" else TIER_BUDGETS
    return budgets[case["tier"]]


def _coordinates(plan: dict[str, Any], scope: str) -> list[dict[str, Any]]:
    coordinates: list[dict[str, Any]] = []
    if scope == "linux-full":
        for case in plan["linux_full"]["cases"]:
            for strategy in case["strategies"]:
                for model_style in case["model_styles"]:
                    coordinates.append(
                        {
                            **case,
                            "strategy": strategy,
                            "model_style": model_style,
                            "seed": plan["linux_full"]["seed"],
                            "repetition": 1,
                        }
                    )
        return coordinates
    for case in plan["representative_cases"]:
        for strategy in case["strategies"]:
            for model_style in case["model_styles"]:
                for seed in case["seeds"]:
                    coordinates.append(
                        {
                            **case,
                            "strategy": strategy,
                            "model_style": model_style,
                            "seed": seed,
                            "repetition": 1,
                        }
                    )
                for seed in case["repeat_seeds"]:
                    for repetition in range(2, int(case["repeat_count"]) + 1):
                        coordinates.append(
                            {
                                **case,
                                "strategy": strategy,
                                "model_style": model_style,
                                "seed": seed,
                                "repetition": repetition,
                            }
                        )
    return coordinates


def _shard_coordinates(
    coordinates: list[dict[str, Any]], *, shard_index: int, shard_count: int
) -> list[dict[str, Any]]:
    if shard_count < 1:
        raise ValueError("shard_count must be at least 1")
    if not 0 <= shard_index < shard_count:
        raise ValueError("shard_index must be between 0 and shard_count - 1")
    return [
        coordinate
        for position, coordinate in enumerate(coordinates)
        if position % shard_count == shard_index
    ]


def run_release_benchmarks(
    *,
    python: Path,
    benchmark_root: Path,
    plan_path: Path,
    data_manifest_path: Path,
    output_dir: Path,
    scope: str,
    shard_index: int = 0,
    shard_count: int = 1,
) -> dict[str, Any]:
    python = Path(os.path.abspath(python))
    benchmark_root = benchmark_root.resolve()
    plan_path = plan_path.resolve()
    data_manifest_path = data_manifest_path.resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    logs_dir = output_dir / "logs"
    logs_dir.mkdir(exist_ok=True)
    reproductions_dir = output_dir / "reproductions"
    reproductions_dir.mkdir(exist_ok=True)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    manifest_errors = verify_data_manifest(
        benchmark_root=benchmark_root, manifest_path=data_manifest_path
    )
    if manifest_errors:
        raise RuntimeError("; ".join(manifest_errors))
    inventory_process = subprocess.run(
        [str(python), str(benchmark_root / "benchmark.py"), "list-cases"],
        cwd=benchmark_root,
        check=True,
        capture_output=True,
        text=True,
    )
    inventory = {
        row["benchmark_id"]: row for row in json.loads(inventory_process.stdout)
    }
    results: list[dict[str, Any]] = []
    coordinates = _shard_coordinates(
        _coordinates(plan, scope),
        shard_index=shard_index,
        shard_count=shard_count,
    )
    for coordinate in coordinates:
        case = inventory[coordinate["benchmark_id"]]
        budget = _budget(case)
        style_label = str(coordinate["model_style"] or "default").replace("/", "-")
        label = (
            f"{case['benchmark_id']}-{coordinate['strategy']}-{style_label}"
            f"-seed{coordinate['seed']}-r{coordinate['repetition']}"
        )
        reproduction_path = reproductions_dir / f"{label}.optrepro"
        command = [
            str(python),
            str(benchmark_root / "benchmark.py"),
            "run",
            "--case",
            case["benchmark_id"],
            "--strategy",
            coordinate["strategy"],
            "--seed",
            str(coordinate["seed"]),
            "--time-limit-s",
            str(budget),
            "--population-size",
            "16",
            "--trace-limit",
            "8",
            "--thread-count",
            "1",
            "--reproduction-path",
            str(reproduction_path),
            "--no-download",
        ]
        if coordinate["model_style"] is not None:
            command.extend(["--model-style", coordinate["model_style"]])
        started = time.perf_counter()
        process, timed_out = _run_process_tree(
            command, cwd=benchmark_root, timeout_s=budget + 15.0
        )
        if timed_out:
            stdout = process.stdout or ""
            stderr = process.stderr or ""
            result = {
                "label": label,
                "benchmark_id": case["benchmark_id"],
                "family": case["family"],
                "tier": case["tier"],
                "seed": coordinate["seed"],
                "repetition": coordinate["repetition"],
                "strategy": coordinate["strategy"],
                "model_style": coordinate["model_style"],
                "status": "FAIL",
                "reason": "hard_timeout",
                "duration_s": time.perf_counter() - started,
            }
        else:
            stdout, stderr = process.stdout, process.stderr
            result = _classify_process(
                process=process,
                label=label,
                case=case,
                seed=coordinate["seed"],
                repetition=coordinate["repetition"],
                strategy=coordinate["strategy"],
                model_style=coordinate["model_style"],
                duration_s=time.perf_counter() - started,
            )
        (logs_dir / f"{label}.stdout.log").write_text(stdout, encoding="utf-8")
        (logs_dir / f"{label}.stderr.log").write_text(stderr, encoding="utf-8")
        if result["status"] == "PASS":
            reproduction_path.unlink(missing_ok=True)
        elif reproduction_path.is_file():
            result["reproduction_path"] = str(reproduction_path.relative_to(output_dir))
        results.append(result)
    results.extend(_reproducibility_warnings(results))
    with (output_dir / "benchmark-results.jsonl").open("w", encoding="utf-8") as stream:
        for result in results:
            stream.write(json.dumps(result, sort_keys=True) + "\n")
    summary = {
        "schema_version": 1,
        "scope": scope,
        "shard_index": shard_index,
        "shard_count": shard_count,
        "coordinate_count": len(coordinates),
        "result_counts": {
            status: sum(result["status"] == status for result in results)
            for status in sorted({result["status"] for result in results})
        },
    }
    (output_dir / "benchmark-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return summary


def _run_process_tree(
    command: list[str], *, cwd: Path, timeout_s: float
) -> tuple[subprocess.CompletedProcess[str], bool]:
    popen_kwargs: dict[str, Any] = {
        "cwd": cwd,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "text": True,
    }
    if os.name == "nt":
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        popen_kwargs["start_new_session"] = True
    process = subprocess.Popen(command, **popen_kwargs)
    try:
        stdout, stderr = process.communicate(timeout=timeout_s)
        timed_out = False
    except subprocess.TimeoutExpired:
        timed_out = True
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                capture_output=True,
                text=True,
                check=False,
            )
        else:
            os.killpg(process.pid, signal.SIGKILL)
        stdout, stderr = process.communicate()
    return subprocess.CompletedProcess(
        command, process.returncode, stdout, stderr
    ), timed_out


def _classify_process(
    *,
    process: subprocess.CompletedProcess[str],
    label: str,
    case: dict[str, Any],
    seed: int,
    repetition: int,
    strategy: str,
    model_style: str | None,
    duration_s: float,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "label": label,
        "benchmark_id": case["benchmark_id"],
        "family": case["family"],
        "tier": case["tier"],
        "seed": seed,
        "repetition": repetition,
        "strategy": strategy,
        "model_style": model_style,
        "duration_s": duration_s,
        "exit_code": process.returncode,
    }
    if process.returncode != 0:
        result.update(status="FAIL", reason="process_exit")
        return result
    try:
        rows = json.loads(process.stdout)
    except json.JSONDecodeError as exc:
        result.update(status="FAIL", reason="invalid_json", message=str(exc))
        return result
    failed_rows = [
        row
        for row in rows
        if row.get("status")
        in {"error", "verification_failed", "observation_verification_failed"}
        or not row.get("feasible")
        or row.get("verification_passed") is False
        or row.get("observation_verification_passed") is False
    ]
    result["rows"] = rows
    result["status"] = "FAIL" if failed_rows else "PASS"
    if failed_rows:
        result["reason"] = "benchmark_verification"
    return result


def _reproducibility_warnings(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str | None, int], list[float | None]] = defaultdict(
        list
    )
    for result in results:
        if result.get("status") != "PASS" or result.get("repetition", 1) < 1:
            continue
        for row in result.get("rows", []):
            grouped[
                (
                    result["benchmark_id"],
                    str(row.get("strategy")),
                    row.get("model_style"),
                    result["seed"],
                )
            ].append(row.get("objective"))
    warnings = []
    for (case_id, strategy, model_style, seed), objectives in grouped.items():
        if len(objectives) < 3:
            continue
        normalized = {json.dumps(value, sort_keys=True) for value in objectives}
        if len(normalized) > 1:
            warnings.append(
                {
                    "label": f"reproducibility-{case_id}-{strategy}-seed{seed}",
                    "benchmark_id": case_id,
                    "strategy": strategy,
                    "model_style": model_style,
                    "seed": seed,
                    "status": "QUALITY_WARNING",
                    "reason": "same_seed_objective_variation",
                    "objectives": objectives,
                }
            )
    return warnings


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--benchmark-root", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--data-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--scope", choices=("representative", "linux-full"), default="representative"
    )
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--shard-count", type=int, default=1)
    args = parser.parse_args(argv)
    summary = run_release_benchmarks(
        python=args.python,
        benchmark_root=args.benchmark_root,
        plan_path=args.plan,
        data_manifest_path=args.data_manifest,
        output_dir=args.output_dir,
        scope=args.scope,
        shard_index=args.shard_index,
        shard_count=args.shard_count,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 1 if summary["result_counts"].get("FAIL", 0) else 0


if __name__ == "__main__":
    raise SystemExit(main())
