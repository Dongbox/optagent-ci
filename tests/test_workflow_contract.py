from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github" / "workflows" / "kernel-regression.yml").read_text(encoding="utf-8")


class WorkflowContractTest(unittest.TestCase):
    def test_uses_current_optagent_python_test_layout(self) -> None:
        self.assertIn("python -m pip install -r requirements-dev.txt", WORKFLOW)
        self.assertIn("python -m pytest -q tests --tb=short", WORKFLOW)
        self.assertIn("working-directory: optagent", WORKFLOW)
        self.assertNotIn("CMakeLists.txt", WORKFLOW)
        self.assertNotIn("regression_snapshot.py", WORKFLOW)

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
