# optagent-ci

Public CI harness for [optagent](https://github.com/Dongbox/optagent) kernel regression testing.

## Purpose

This repository runs cross-compiler determinism regression tests against the private `optagent` C++ kernel using **free** GitHub Actions minutes (public repos have unlimited standard runner minutes).

The key guarantee: **same architecture + same seed → same result, regardless of compiler (GCC vs Clang vs MSVC).**

## CI Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  Phase 1: Generate golden fixtures (GCC 13, x86_64)                │
│  → Builds kernel, runs solve cases with fixed seeds                │
│  → Saves results as golden fixtures (artifact)                     │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ artifact: golden-fixtures-x86_64
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Phase 2: Cross-compiler verification (same x86_64 architecture)   │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │ GCC 13 -O2   │  │ Clang 18 -O2 │  │ GCC 13 ASan+UBSan       │  │
│  │ (baseline)   │  │ (cross-check)│  │ (memory safety)          │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────────┘  │
│         │                  │                     │                   │
│         ▼                  ▼                     ▼                   │
│  Compare against golden: must be bit-exact                          │
│  Any difference = compiler-induced UB or non-determinism bug        │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ on failure
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Auto-diagnosis: scripts/dev/diagnose_divergence.py                 │
│  → Re-runs with iteration trace (Layer 2)                          │
│  → Binary-searches first divergence point                          │
│  → Classifies root cause (rng_drift / evaluation_path / ...)       │
│  → Outputs report + uploads as artifact                            │
└─────────────────────────────────────────────────────────────────────┘
```

## Test Matrix

| Platform | Compiler | Optimization | Trigger | Verification |
|----------|----------|-------------|---------|--------------|
| Linux x86_64 | GCC 13 | -O2 | always | golden generation + comparison |
| Linux x86_64 | Clang 18 | -O2 | always | comparison against golden |
| Linux x86_64 | GCC 13 | -O1 + ASan+UBSan | always | comparison + memory safety |
| Linux x86_64 | GCC 14 | -O3 -flto | weekly | comparison against golden |
| Linux x86_64 | Clang 18 | -O3 -flto=thin | weekly | comparison against golden |
| macOS arm64 | Apple Clang | -O2 | weekly | self-consistency only |
| Windows x64 | MSVC 2022 | /O2 | weekly | self-consistency only |

### Verification Levels

- **Golden comparison** (Linux x86_64): fixed seed → exact match on objective value, variable assignments, and iteration count. Any difference between GCC and Clang indicates a real bug (UB, uninitialized memory, or non-deterministic code path).
- **Self-consistency** (macOS/Windows): same-process repeated solve must produce identical results. Does not compare against x86_64 golden because cross-architecture differences are expected (platform-dependent `std::hash`, `std::uniform_int_distribution`).

## Divergence Diagnosis Report Format

When tests fail, the auto-diagnosis generates a JSON report (`diagnosis.json`) with this structure:

```json
{
  "timestamp": "2026-07-03 05:06:17 UTC",
  "environment": {
    "platform": "Linux",
    "arch": "x86_64",
    "python": "3.12.3"
  },
  "cases": [
    {
      "case_name": "tsp_5_ga_seed42",
      "has_divergence": true,
      "classification": {
        "category": "rng_drift | evaluation_path | search_depth | termination_timing | solution_symmetry",
        "confidence": "high | medium | low",
        "summary": "Human-readable one-line conclusion",
        "evidence": ["Supporting observations..."],
        "code_locations": ["cpp/file.cc — what to investigate"],
        "suggested_actions": ["Step-by-step debugging guide"]
      },
      "golden": {"objective_value": 19.0, "iterations": 373},
      "actual": {"objective_value": 19.0, "iterations": 389}
    }
  ],
  "overall_conclusion": "Cross-case summary...",
  "cross_case_pattern": "GA-only | ALNS-only | shared infrastructure"
}
```

### Diagnosis Categories

| Category | Meaning | Typical Root Cause |
|----------|---------|-------------------|
| `rng_drift` | RNG state diverged between compilers | Conditional RNG consumption, uninitialized branch |
| `evaluation_path` | Same operator, different score | Floating-point UB, unordered container iteration |
| `search_depth` | Construct/seeding phase differs | Platform-dependent initialization |
| `termination_timing` | Different iteration count, same objective | Construct-phase iteration counting |
| `solution_symmetry` | Same objective, different variables | Multiple optima (acceptable) |

## Setup

### 1. Create a fine-grained PAT

- GitHub → Settings → Developer settings → Fine-grained personal access tokens
- Scope: `Dongbox/optagent` only
- Permissions: `Contents: Read`

### 2. Add the secret

- This repo → Settings → Secrets → Actions → `PRIVATE_REPO_PAT`

### 3. (Optional) Trigger from private repo

```yaml
# In private repo: .github/workflows/trigger-regression.yml
- name: Trigger regression CI
  run: |
    gh workflow run kernel-regression.yml \
      --repo Dongbox/optagent-ci \
      --ref main \
      -f ref=${{ github.sha }}
  env:
    GH_TOKEN: ${{ secrets.CI_DISPATCH_TOKEN }}
```

## Security

- PAT has read-only access to the private repo
- Secrets never exposed to fork PRs (GitHub default)
- Build logs contain compiler output only, not source code
- macOS/Windows jobs only run self-consistency (no golden fixture download)
