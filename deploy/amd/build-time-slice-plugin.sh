#!/usr/bin/env bash
# Build the hami-learning-cloud AMD time-slicing device plugin.
#
# Usage:
#   ./deploy/amd/build-time-slice-plugin.sh [output-binary]
#
# Environment:
#   GH_PROXY  Optional GitHub proxy prefix, default https://gh-proxy.com
#             Set GH_PROXY="" to clone directly from GitHub.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UPSTREAM_COMMIT="ed7646843003e8f0b6a0630346f01bb4d1ecff2e"
GH_PROXY="${GH_PROXY:-https://gh-proxy.com}"
OUT="${1:-${SCRIPT_DIR}/dist/k8s-device-plugin}"
CLONE_DIR="$(mktemp -d)"

trap 'rm -rf "$CLONE_DIR"' EXIT

if [[ -n "$GH_PROXY" ]]; then
  CLONE_URL="${GH_PROXY%/}/https://github.com/ROCm/k8s-device-plugin"
else
  CLONE_URL="https://github.com/ROCm/k8s-device-plugin"
fi

command -v go >/dev/null || { echo "go is required" >&2; exit 1; }
command -v git >/dev/null || { echo "git is required" >&2; exit 1; }

echo "cloning ROCm/k8s-device-plugin @ ${UPSTREAM_COMMIT}"
git clone --depth 1 --branch "$UPSTREAM_COMMIT" "$CLONE_URL" "$CLONE_DIR"

echo "applying hami-learning-cloud time-slice patch"
git -C "$CLONE_DIR" apply "${SCRIPT_DIR}/amd-time-slice.patch"

echo "building static binary -> ${OUT}"
mkdir -p "$(dirname "$OUT")"
CGO_ENABLED=0 GOFLAGS=-mod=vendor go -C "$CLONE_DIR" build -o "$OUT" ./cmd/k8s-device-plugin
chmod +x "$OUT"

echo "done: $OUT"
