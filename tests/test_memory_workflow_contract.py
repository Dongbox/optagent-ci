from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github" / "workflows" / "memory-sanitizers.yml").read_text(encoding="utf-8")


class MemoryWorkflowContractTest(unittest.TestCase):
    def test_checks_out_an_exact_optagent_revision(self) -> None:
        self.assertIn("Full 40-character optagent commit SHA", WORKFLOW)
        self.assertIn("repository: Dongbox/optagent", WORKFLOW)
        self.assertIn("ref: ${{ needs.resolve.outputs.sha }}", WORKFLOW)
        self.assertIn("persist-credentials: false", WORKFLOW)

    def test_uses_repository_owned_sanitizer_preset(self) -> None:
        self.assertIn("cmake --preset kernel-asan-ninja", WORKFLOW)
        self.assertIn("cmake --build --preset kernel-asan-ninja", WORKFLOW)
        self.assertNotIn("-fsanitize=address,undefined", WORKFLOW)

    def test_enables_leak_and_undefined_behavior_failures(self) -> None:
        self.assertIn("detect_leaks=1:halt_on_error=1", WORKFLOW)
        self.assertIn("UBSAN_OPTIONS", WORKFLOW)
        self.assertIn("ctest --test-dir build/kernel-asan-ninja --output-on-failure", WORKFLOW)

    def test_reports_a_dedicated_commit_status(self) -> None:
        self.assertIn("optagent-ci/memory-sanitizers", WORKFLOW)
        self.assertIn("repos/Dongbox/optagent/statuses/${SHA}", WORKFLOW)


if __name__ == "__main__":
    unittest.main()
