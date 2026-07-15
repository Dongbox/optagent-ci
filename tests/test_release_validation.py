from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import textwrap
import unittest
from unittest import mock

from scripts.aggregate_release_validation import aggregate
from scripts.run_release_benchmarks import (
    _classify_process,
    _run_process_tree,
    _shard_coordinates,
    verify_data_manifest,
)


class ReleaseValidationTest(unittest.TestCase):
    def test_benchmark_shards_partition_coordinates_without_overlap(self) -> None:
        coordinates = [{"id": index} for index in range(35)]

        shards = [
            _shard_coordinates(coordinates, shard_index=index, shard_count=16)
            for index in range(16)
        ]

        self.assertEqual([row["id"] for row in shards[0]], [0, 16, 32])
        self.assertEqual([row["id"] for row in shards[15]], [15, 31])
        self.assertEqual(
            sorted(row["id"] for shard in shards for row in shard),
            list(range(35)),
        )

    def test_benchmark_shards_reject_invalid_bounds(self) -> None:
        with self.assertRaisesRegex(ValueError, "shard_count"):
            _shard_coordinates([], shard_index=0, shard_count=0)
        with self.assertRaisesRegex(ValueError, "shard_index"):
            _shard_coordinates([], shard_index=2, shard_count=2)

    def test_benchmark_process_requires_feasible_verified_rows(self) -> None:
        process = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(
                [{"status": "feasible", "feasible": True, "verification_passed": True}]
            ),
            stderr="",
        )

        result = _classify_process(
            process=process,
            label="case",
            case={"benchmark_id": "case", "family": "family", "tier": "smoke"},
            seed=11,
            repetition=1,
            strategy="ga",
            model_style=None,
            duration_s=1.0,
        )

        self.assertEqual(result["status"], "PASS")

    def test_process_tree_runner_enforces_hard_timeout(self) -> None:
        process, timed_out = _run_process_tree(
            [sys.executable, "-c", "import time; time.sleep(10)"],
            cwd=Path.cwd(),
            timeout_s=0.05,
        )

        self.assertTrue(timed_out)
        self.assertNotEqual(process.returncode, 0)

    def test_release_driver_resolves_relative_paths_before_changing_cwd(self) -> None:
        from scripts.run_release_benchmarks import run_release_benchmarks

        root = Path(self.id().replace(".", "-"))
        original_cwd = Path.cwd()
        try:
            benchmark_root = root / "benchmark-repo"
            raw = benchmark_root / "benchmarks" / "cases" / "family" / "raw"
            raw.mkdir(parents=True)
            data_file = raw / "case.dat"
            data_file.write_text("data", encoding="utf-8")
            (benchmark_root / "benchmark.py").write_text(
                textwrap.dedent(
                    """
                    import argparse
                    import json
                    from pathlib import Path
                    import sys

                    if sys.argv[1] == "list-cases":
                        print(json.dumps([{"benchmark_id": "case", "family": "exact_linear_mip", "tier": "smoke"}]))
                    else:
                        parser = argparse.ArgumentParser()
                        parser.add_argument("command")
                        parser.add_argument("--case")
                        parser.add_argument("--strategy")
                        parser.add_argument("--seed")
                        parser.add_argument("--time-limit-s")
                        parser.add_argument("--population-size")
                        parser.add_argument("--trace-limit")
                        parser.add_argument("--thread-count")
                        parser.add_argument("--reproduction-path")
                        parser.add_argument("--no-download", action="store_true")
                        args = parser.parse_args()
                        Path(args.reproduction_path).write_text("capture", encoding="utf-8")
                        print(json.dumps([{"status": "optimal", "feasible": True, "verification_passed": True, "strategy": args.strategy, "objective": 1}]))
                    """
                ),
                encoding="utf-8",
            )
            plan = root / "plan.json"
            plan.write_text(
                json.dumps(
                    {
                        "representative_cases": [
                            {
                                "benchmark_id": "case",
                                "family": "exact_linear_mip",
                                "tier": "smoke",
                                "strategies": ["optx"],
                                "model_styles": [None],
                                "seeds": [0],
                                "repeat_seeds": [],
                                "repeat_count": 1,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            import hashlib

            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "files": [
                            {
                                "path": "family/raw/case.dat",
                                "sha256": hashlib.sha256(
                                    data_file.read_bytes()
                                ).hexdigest(),
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            os.chdir(root)

            summary = run_release_benchmarks(
                python=Path(sys.executable),
                benchmark_root=Path("benchmark-repo"),
                plan_path=Path("plan.json"),
                data_manifest_path=Path("manifest.json"),
                output_dir=Path("evidence"),
                scope="representative",
            )

            self.assertEqual(summary["result_counts"], {"PASS": 1})
            self.assertFalse(
                any((root / "evidence" / "reproductions").glob("*.optrepro"))
            )
        finally:
            os.chdir(original_cwd)
            import shutil

            shutil.rmtree(root, ignore_errors=True)

    @unittest.skipIf(os.name == "nt", "symlink behavior is covered by macOS and Linux")
    def test_release_driver_preserves_virtualenv_python_symlink(self) -> None:
        from scripts.run_release_benchmarks import run_release_benchmarks

        root = Path(self.id().replace(".", "-"))
        try:
            benchmark_root = root / "benchmark-repo"
            benchmark_root.mkdir(parents=True)
            python = root / "venv" / "bin" / "python"
            python.parent.mkdir(parents=True)
            python.symlink_to(Path(sys.executable))
            plan = root / "plan.json"
            plan.write_text(json.dumps({"representative_cases": []}), encoding="utf-8")
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"files": []}), encoding="utf-8")
            inventory = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="[]", stderr=""
            )

            with mock.patch(
                "scripts.run_release_benchmarks.subprocess.run", return_value=inventory
            ) as run:
                run_release_benchmarks(
                    python=python,
                    benchmark_root=benchmark_root,
                    plan_path=plan,
                    data_manifest_path=manifest,
                    output_dir=root / "evidence",
                    scope="representative",
                )

            self.assertEqual(run.call_args.args[0][0], str(python.absolute()))
            self.assertNotEqual(run.call_args.args[0][0], str(python.resolve()))
        finally:
            import shutil

            shutil.rmtree(root, ignore_errors=True)

    def test_data_manifest_detects_changes(self) -> None:
        root = Path(self.id().replace(".", "-"))
        try:
            raw = root / "benchmarks" / "cases" / "family" / "raw"
            raw.mkdir(parents=True)
            path = raw / "case.dat"
            path.write_text("data", encoding="utf-8")
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {"files": [{"path": "family/raw/case.dat", "sha256": "bad"}]}
                ),
                encoding="utf-8",
            )

            self.assertEqual(
                verify_data_manifest(benchmark_root=root, manifest_path=manifest),
                ["benchmark data checksum mismatch: family/raw/case.dat"],
            )
        finally:
            import shutil

            shutil.rmtree(root, ignore_errors=True)

    def test_aggregate_reports_pass_with_gaps(self) -> None:
        root = Path(self.id().replace(".", "-"))
        try:
            artifact = root / "artifact"
            artifact.mkdir(parents=True)
            (artifact / "results.jsonl").write_text(
                json.dumps({"scenario": "api", "status": "PASS"})
                + "\n"
                + json.dumps(
                    {"scenario": "release-positive-license", "status": "NOT_COVERED"}
                )
                + "\n",
                encoding="utf-8",
            )

            summary = aggregate(artifacts_root=root, output_dir=root / "summary")

            self.assertEqual(summary["conclusion"], "PASS_WITH_GAPS")
            self.assertIn(
                "`artifact`",
                (root / "summary" / "summary.md").read_text(encoding="utf-8"),
            )
        finally:
            import shutil

            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
