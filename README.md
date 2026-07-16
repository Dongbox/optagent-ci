# optagent-ci

External regression harness for the OptAgent native kernel.

## Guarantees

The harness enforces two different reproducibility contracts:

- The same binary, problem, seed, and iteration budget must produce an identical complete snapshot.
- Different compilers must produce semantically equivalent results. Feasibility, replay validation, status category, and objective value are gating; assignments, iteration counts, and search traces are diagnostic.

Integer objectives compare exactly. Floating objectives use `abs_tol=1e-9` and `rel_tol=1e-9`.

## Regression Workflow

The regression workflow is manual-only. Dispatch it with one exact 40-character
OptAgent commit SHA. It checks out that revision, builds the v1.2 native kernel
with GCC 13, runs the C++ owner tests and Python regression/contract tests, and
writes
`optagent-ci/regression` back to the tested OptAgent commit.

The workflow installs Python test dependencies directly and does not install
`highspy`; v1.2 embeds the HiGHS native library through CMake.

Performance regression remains owned by `optagent-benchmarks`.

## Native Memory Sanitizers

`memory-sanitizers.yml` is a dedicated Linux native-memory gate. It accepts an exact OptAgent commit SHA, builds the repository-owned `kernel-asan-ninja` preset with GCC 13, and runs the C++ owner tests with AddressSanitizer, UndefinedBehaviorSanitizer, and LeakSanitizer enabled. It does not run Python/pybind tests, so Python dynamic loading cannot mask native leak results.

The workflow runs every Monday and can also be dispatched manually. It publishes the `optagent-ci/memory-sanitizers` status to the tested OptAgent commit.

## One-Off Release Validation

`release-validation.yml` is a manually dispatched Python 3.12 release evidence flow for Linux x86_64, macOS arm64, and Windows x64. It accepts one exact OptAgent commit SHA and uses the same private-repository read boundary as the regression workflow.

Each platform builds two wheels from that SHA:

- a validation wheel trusting a job-local ephemeral key, used for a complete machine request, short-lived `core + exact` license, public API validation, and benchmark execution;
- a release wheel trusting the repository production public key, used for packaging, native loading, and license rejection-path validation.

The release wheel is uploaded. The validation wheel and its private key are deleted and are never artifacts. Because no production signing service participates, a positive solve using the release wheel remains explicitly `NOT_COVERED`, so the strongest possible conclusion is `PASS_WITH_GAPS`.

Benchmark data is prepared once, hashed, distributed to all three platform jobs, and consumed with downloads disabled. The representative matrix covers two cases from each implemented family with ten fixed seeds; Linux also runs the complete registered inventory once.

## OptAgent Contract

OptAgent owns the scenarios and native replay logic in:

```text
scripts/tests/regression_snapshot.py
tests/python/regression/
tests/python/integration/kernel_contract/
tests/cpp/
```

This repository owns compiler/platform orchestration, semantic comparison, artifacts, and commit-status reporting.

## Required Secrets

Use fine-grained tokens with only the listed permissions.

### In `Dongbox/optagent`

`OPTAGENT_CI_TOKEN`:

- Repository: `Dongbox/optagent-ci`
- Actions: write

The repository `GITHUB_TOKEN` writes pending or not-applicable status to its own commit.

### In `Dongbox/optagent-ci`

`OPTAGENT_REPO_TOKEN`:

- Repository: `Dongbox/optagent`
- Contents: read
- Commit statuses: write

Checkout uses `persist-credentials: false`. Workflows accept only commits that belong to `Dongbox/optagent`.

## Required-Check Enforcement

The workflow always publishes the `optagent-ci/regression` commit status. To make it a merge-blocking required check, protect the OptAgent `main` branch and require that status context.

At the time this harness was updated, `Dongbox/optagent` was a private repository on a GitHub plan that did not expose branch protection or repository rulesets. In that configuration the status is advisory, not merge-blocking. Upgrade the plan or make the repository public before claiming enforcement.

## Local Validation

```bash
python3 -m unittest discover -s tests -v
python3 scripts/compare_snapshots.py \
  --baseline /path/to/gcc.json \
  --candidate /path/to/clang.json
```
