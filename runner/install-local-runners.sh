#!/usr/bin/env bash
set -euo pipefail

REPOSITORY="${REPOSITORY:-Dongbox/optagent-ci}"
RUNNER_ROOT="${RUNNER_ROOT:-${HOME}/.local/share/optagent-ci-runners}"
RUNNER_VERSION="2.337.0"
MACOS_SHA256="5a2cd92908a93d7276a194e1de6008099f3e7946f3f8e14aa7a1a7b4a31fdec2"
LINUX_SHA256="70920811a4f8ad4328818682bca5c6469c1c942fab52448868071d0063816613"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
  cat <<'EOF'
Usage: runner/install-local-runners.sh [macos|linux|all]

Install repository-scoped GitHub Actions runners for Dongbox/optagent-ci.
Linux uses an amd64 Ubuntu container; macOS uses the current arm64 host.

Environment: REPOSITORY and RUNNER_ROOT may be overridden.
EOF
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || { printf 'Required command not found: %s\n' "$1" >&2; exit 1; }
}

download_runner() {
  local os_arch="$1" expected="$2" destination="$3" archive url actual
  archive="$(mktemp "${TMPDIR:-/tmp}/actions-runner.XXXXXX.tar.gz")"
  url="https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-${os_arch}-${RUNNER_VERSION}.tar.gz"
  curl --fail --location --silent --show-error "${url}" --output "${archive}"
  actual="$(shasum -a 256 "${archive}" | awk '{print $1}')"
  [[ "${actual}" == "${expected}" ]] || { rm -f "${archive}"; printf 'Checksum mismatch for %s\n' "${url}" >&2; exit 1; }
  mkdir -p "${destination}"
  tar -xzf "${archive}" -C "${destination}"
  rm -f "${archive}"
}

registration_token() {
  gh api --method POST "repos/${REPOSITORY}/actions/runners/registration-token" --jq .token
}

install_macos() {
  local destination token
  [[ "$(uname -s)" == Darwin && "$(uname -m)" == arm64 ]] || { printf 'The macOS runner requires a macOS arm64 host.\n' >&2; exit 1; }
  destination="${RUNNER_ROOT}/macos-arm64"
  [[ -x "${destination}/config.sh" ]] || download_runner "osx-arm64" "${MACOS_SHA256}" "${destination}"
  if [[ ! -f "${destination}/.runner" ]]; then
    token="$(registration_token)"
    (cd "${destination}" && ./config.sh --unattended --replace --url "https://github.com/${REPOSITORY}" --token "${token}" --name "$(hostname -s)-macos-arm64" --labels "optagent-ci,macos-arm64" --work _work)
  fi
  (cd "${destination}" && ./svc.sh install && ./svc.sh start)
}

install_linux() {
  local destination image token socket
  require_command docker
  destination="${RUNNER_ROOT}/linux-amd64"
  image="optagent-ci-runner-linux-amd64:${RUNNER_VERSION}"
  socket="$(docker context inspect --format '{{ (index .Endpoints "docker").Host }}')"
  socket="${socket#unix://}"
  [[ -S "${socket}" ]] || { printf 'The active Docker context does not expose a Unix socket: %s\n' "${socket}" >&2; exit 1; }
  [[ -x "${destination}/config.sh" ]] || download_runner "linux-x64" "${LINUX_SHA256}" "${destination}"
  docker build --platform linux/amd64 --tag "${image}" --file "${SCRIPT_DIR}/Dockerfile.linux-amd64" "${SCRIPT_DIR}"
  if [[ ! -f "${destination}/.runner" ]]; then
    token="$(registration_token)"
    docker run --rm --platform linux/amd64 --volume "${destination}:${destination}" --workdir "${destination}" "${image}" ./config.sh --unattended --replace --url "https://github.com/${REPOSITORY}" --token "${token}" --name "$(hostname -s)-linux-amd64" --labels "optagent-ci,linux-amd64" --work _work
    unset token
  fi
  docker rm --force optagent-ci-linux-amd64 >/dev/null 2>&1 || true
  docker run --detach --restart unless-stopped --platform linux/amd64 --name optagent-ci-linux-amd64 --volume "${destination}:${destination}" --volume "${socket}:/var/run/docker.sock" --workdir "${destination}" "${image}" ./run.sh
}

require_command curl
require_command gh
require_command shasum
gh auth status --hostname github.com >/dev/null
mkdir -p "${RUNNER_ROOT}"

case "${1:-all}" in
  macos) install_macos ;;
  linux) install_linux ;;
  all) install_macos; install_linux ;;
  -h|--help) usage ;;
  *) usage >&2; exit 2 ;;
esac
