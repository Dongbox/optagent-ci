from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github" / "workflows" / "kernel-regression.yml").read_text(encoding="utf-8")


class WorkflowContractTest(unittest.TestCase):
    def test_runs_linux_and_windows_amd64_snapshots(self) -> None:
        self.assertIn("optagent/tests/python/regression", WORKFLOW)
        self.assertIn("optagent/tests/python/integration/kernel_contract", WORKFLOW)
        self.assertIn("optagent/scripts/tests/regression_snapshot.py", WORKFLOW)
        self.assertIn("-DOPTAGENT_BUILD_CPP_TESTS=ON", WORKFLOW)
        self.assertIn("cryptography>=43,<46", WORKFLOW)
        self.assertNotIn("highspy", WORKFLOW)
        self.assertIn("runs-on: windows-latest", WORKFLOW)
        self.assertIn("arch: x64", WORKFLOW)
        self.assertIn("regression-snapshot-linux-amd64-", WORKFLOW)
        self.assertIn("regression-snapshot-windows-amd64-", WORKFLOW)
        self.assertIn("Compare Linux and Windows semantic snapshots", WORKFLOW)
        self.assertIn("scripts/compare_snapshots.py", WORKFLOW)

    def test_is_manual_only(self) -> None:
        self.assertIn("workflow_dispatch:", WORKFLOW)
        self.assertNotIn("  schedule:", WORKFLOW)
        self.assertNotIn("  push:", WORKFLOW)

    def test_checks_out_and_reports_an_exact_sha(self) -> None:
        self.assertIn("Full 40-character optagent commit SHA", WORKFLOW)
        self.assertIn("persist-credentials: false", WORKFLOW)
        self.assertIn("optagent-ci/regression", WORKFLOW)
        self.assertIn("repos/Dongbox/optagent/statuses/${SHA}", WORKFLOW)
        self.assertIn("Fail workflow when regression failed", WORKFLOW)


if __name__ == "__main__":
    unittest.main()
