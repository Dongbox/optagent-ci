from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github" / "workflows" / "release-validation.yml").read_text(
    encoding="utf-8"
)
REGRESSION = (ROOT / ".github" / "workflows" / "kernel-regression.yml").read_text(
    encoding="utf-8"
)


class ReleaseWorkflowContractTest(unittest.TestCase):
    def test_release_validation_uses_exact_sha_python312_and_three_native_platforms(
        self,
    ) -> None:
        self.assertIn("Full 40-character OptAgent commit SHA", WORKFLOW)
        self.assertIn('PYTHON_VERSION: "3.12"', WORKFLOW)
        self.assertIn("runs-on: ubuntu-latest", WORKFLOW)
        self.assertIn("runs-on: macos-14", WORKFLOW)
        self.assertIn("runs-on: windows-latest", WORKFLOW)
        self.assertIn("persist-credentials: false", WORKFLOW)
        self.assertIn(
            "group: release-validation-${{ inputs.optagent_sha }}-${{ github.sha }}",
            WORKFLOW,
        )

    def test_release_validation_initializes_only_the_required_submodule(self) -> None:
        self.assertNotIn("submodules: recursive", WORKFLOW)
        self.assertEqual(
            WORKFLOW.count(
                "git -C optagent submodule update --init --depth 1 benchmarks"
            ),
            5,
        )

    def test_release_validation_builds_two_wheels_and_never_uploads_validation_wheels(
        self,
    ) -> None:
        self.assertIn("validation_license.py generate-key", WORKFLOW)
        self.assertIn("release_wheel_positive_license", WORKFLOW)
        self.assertIn("release-validation-linux/release/optagent-*.whl", WORKFLOW)
        self.assertNotIn(
            "release-validation-linux/validation/optagent-*.whl\n          if-no-files-found",
            WORKFLOW,
        )
        self.assertIn("Remove validation signing material", WORKFLOW)
        self.assertIn("Remove shard validation signing material", WORKFLOW)
        self.assertIn(
            'default: "[0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,59,60,61,62,63]"',
            WORKFLOW,
        )
        self.assertIn("shard: ${{ fromJSON(inputs.linux_full_shards) }}", WORKFLOW)
        self.assertIn("--shard-count 64", WORKFLOW)
        self.assertIn("retry_linux_full_only:", WORKFLOW)
        self.assertEqual(
            WORKFLOW.count('if: ${{ !inputs.retry_linux_full_only }}'), 4
        )
        self.assertIn(
            "if: ${{ always() && !inputs.retry_linux_full_only }}", WORKFLOW
        )

    def test_release_validation_uses_offline_benchmark_plan_and_hard_timeout_driver(
        self,
    ) -> None:
        self.assertIn("release-plan", WORKFLOW)
        self.assertIn("--prepare-data", WORKFLOW)
        self.assertIn(
            "--no-download",
            (ROOT / "scripts" / "run_release_benchmarks.py").read_text(
                encoding="utf-8"
            ),
        )
        self.assertIn(
            "budget + 15.0",
            (ROOT / "scripts" / "run_release_benchmarks.py").read_text(
                encoding="utf-8"
            ),
        )
        driver = (ROOT / "scripts" / "run_release_benchmarks.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("os.killpg", driver)
        self.assertIn("taskkill", driver)

    def test_benchmarks_reuse_the_installed_license_configuration(self) -> None:
        self.assertEqual(
            WORKFLOW.count('export XDG_CONFIG_HOME="${HOME}/.config"'), 8
        )

    def test_regression_workflow_uses_current_kernel_target(self) -> None:
        self.assertIn("--target _optagent_kernel", REGRESSION)
        self.assertNotIn("--target _optagent_native", REGRESSION)


if __name__ == "__main__":
    unittest.main()
