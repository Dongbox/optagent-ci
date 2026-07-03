# optagent-ci

Public CI harness for [optagent](https://github.com/Dongbox/optagent) kernel regression testing.

## Purpose

This repository runs cross-compiler, cross-optimization regression tests against the private `optagent` C++ kernel using **free** GitHub Actions minutes (public repos have unlimited standard runner minutes).

## How It Works

1. Workflows clone the private `optagent` repo using a fine-grained PAT (`PRIVATE_REPO_PAT` secret)
2. Build the C++ kernel extension with different compiler/optimization combinations
3. Run the full kernel test suite to verify correctness across toolchains

## Test Matrix

| Platform | Compiler | Optimization | Trigger |
|----------|----------|-------------|---------|
| Linux | GCC 13 | `-O2` | PR / push |
| Linux | Clang 18 | `-O2` | PR / push |
| Linux | GCC 13 | `-O1 -fsanitize=address,undefined` | PR / push |
| Linux | GCC 14 | `-O3 -flto` | weekly |
| Linux | Clang 18 | `-O3 -flto=thin` | weekly |
| macOS | Apple Clang | `-O2` | weekly |
| Windows | MSVC 2022 | `/O2` | weekly |

## Setup

### 1. Create a fine-grained PAT

- Go to GitHub → Settings → Developer settings → Fine-grained personal access tokens
- Scope: `Dongbox/optagent` only
- Permissions: `Contents: Read`
- Copy the token

### 2. Add the secret

- Go to this repo → Settings → Secrets and variables → Actions
- Create `PRIVATE_REPO_PAT` with the token value

### 3. (Optional) Dispatch from private repo

Add a step in the private repo to trigger regression on push:

```yaml
- name: Trigger regression CI
  run: |
    gh workflow run kernel-regression.yml \
      --repo Dongbox/optagent-ci \
      -f ref=${{ github.sha }}
  env:
    GH_TOKEN: ${{ secrets.CI_DISPATCH_TOKEN }}
```

## Security

- The PAT only has read access to the private repo
- Secrets are **never** exposed to fork PRs (GitHub default behavior)
- Build logs only contain compiler output, not source code
- Only push/schedule/workflow_dispatch events can access secrets
