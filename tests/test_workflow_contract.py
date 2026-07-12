from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github" / "workflows" / "kernel-regression.yml").read_text(encoding="utf-8")


class WorkflowContractTest(unittest.TestCase):
    def test_uses_current_optagent_test_layout_and_snapshot_contract(self) -> None:
        self.assertIn("optagent/tests/python/regression", WORKFLOW)
        self.assertIn("optagent/tests/python/integration/kernel_contract", WORKFLOW)
        self.assertIn("optagent/scripts/tests/regression_snapshot.py", WORKFLOW)
        self.assertNotIn("tests/regression/", WORKFLOW)
        self.assertNotIn("GENERATE_GOLDEN", WORKFLOW)

    def test_python_path_exposes_optagent_root_for_shared_test_helpers(self) -> None:
        self.assertIn(
            "${{ github.workspace }}/optagent:${{ github.workspace }}/optagent/src",
            WORKFLOW,
        )
        self.assertIn(
            "${GITHUB_WORKSPACE}/optagent:${GITHUB_WORKSPACE}/optagent/src",
            WORKFLOW,
        )
        self.assertIn(
            "$env:GITHUB_WORKSPACE\\optagent;$env:GITHUB_WORKSPACE\\optagent\\src",
            WORKFLOW,
        )

    def test_runs_native_owner_tests_and_instruments_core_via_global_flags(self) -> None:
        self.assertIn("-DOPTAGENT_BUILD_CPP_TESTS=ON", WORKFLOW)
        self.assertIn("ctest --test-dir build/gcc-fast --output-on-failure", WORKFLOW)
        self.assertNotIn("ctest --test-dir build/gcc-fast -R", WORKFLOW)
        self.assertIn("-fsanitize=address,undefined", WORKFLOW)
        self.assertNotIn("target_compile_options(_optagent_native", WORKFLOW)

    def test_checks_out_and_reports_an_exact_sha(self) -> None:
        self.assertIn("Full 40-character optagent commit SHA", WORKFLOW)
        self.assertIn("persist-credentials: false", WORKFLOW)
        self.assertIn("optagent-ci/regression", WORKFLOW)
        self.assertIn("repos/Dongbox/optagent/statuses/${SHA}", WORKFLOW)
        self.assertIn("Fail workflow when regression failed", WORKFLOW)

    def test_weekly_macos_job_requires_arm64(self) -> None:
        self.assertIn("runs-on: macos-14", WORKFLOW)
        self.assertIn('test "$(uname -m)" = arm64', WORKFLOW)


if __name__ == "__main__":
    unittest.main()
