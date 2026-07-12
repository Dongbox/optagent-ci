# optagent-ci

External regression harness for the OptAgent native kernel.

## Guarantees

The harness enforces two different reproducibility contracts:

- The same binary, problem, seed, and iteration budget must produce an identical complete snapshot.
- Different compilers must produce semantically equivalent results. Feasibility, replay validation, status category, and objective value are gating; assignments, iteration counts, and search traces are diagnostic.

Integer objectives compare exactly. Floating objectives use `abs_tol=1e-9` and `rel_tol=1e-9`.

## Fast Gate

Relevant OptAgent changes dispatch an exact 40-character commit SHA.

1. GCC 13 builds the extension and C++ tests.
2. CTest runs the native owner suite.
3. Pytest runs regression, kernel-contract, and representative public solve tests.
4. GCC produces a JSON semantic snapshot.
5. Clang 18 builds the same SHA and produces another snapshot.
6. `scripts/compare_snapshots.py` applies the semantic comparison contract.
7. The workflow writes `optagent-ci/regression` back to the tested OptAgent commit.

## Weekly Full Matrix

The Sunday schedule resolves the current OptAgent `main` SHA and additionally runs:

| Platform | Configuration |
| --- | --- |
| Linux | GCC 13 with ASan and UBSan |
| Linux | GCC 14 with `-O3` and LTO |
| Linux | Clang 18 with `-O3` and ThinLTO |
| macOS arm64 | Apple Clang Release |
| Windows x64 | MSVC Release |

Each platform runs CTest and fixed-seed self-consistency. Linux variants also compare their semantic snapshots with the GCC fast baseline.

Performance regression remains owned by `optagent-benchmarks`.

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
