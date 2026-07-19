#!/usr/bin/env bash
# Run the kernel gate without ever adding rules to the host network namespace.
set -euo pipefail

workspace=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
namespace="secmon-p4-$$_$RANDOM"
nft_binary=""
if [[ -x /usr/sbin/nft ]]; then
  nft_binary=/usr/sbin/nft
else
  nft_binary=$(command -v nft || true)
fi

if [[ -z "$nft_binary" ]]; then
  echo "SKIP: nft is not installed" >&2
  exit 77
fi

host_secmon_present() {
  "$nft_binary" list table inet secmon >/dev/null 2>&1
}

# A host SecMon table is evidence that the script is being aimed at a live
# deployment.  Refuse rather than risk interpreting its state as test output.
if host_secmon_present; then
  echo "REFUSE: host inet secmon already exists" >&2
  exit 2
fi

run_netns() {
  ip netns add "$namespace"
  trap 'ip netns delete "$namespace" 2>/dev/null || true' EXIT
  ip netns exec "$namespace" env PYTHONPATH="$workspace" NFT_BINARY="$nft_binary" \
    python3 "$workspace/scripts/p4_real_kernel_runtime_driver.py"
  ip netns exec "$namespace" env PYTHONPATH="$workspace" NFT_BINARY="$nft_binary" \
    python3 "$workspace/scripts/p4_backend_restart_runtime.py"
  ip netns delete "$namespace"
  trap - EXIT
}

run_container() {
  local engine=$1 image=${P4_RUNTIME_IMAGE:-debian:stable-slim}
  "$engine" info --format '{{json .SecurityOptions}}' | grep -qi rootless && {
    echo "SKIP: $engine is rootless; a rootful isolated runtime is required" >&2
    exit 77
  }
  "$engine" run --rm --network none --cap-add=NET_ADMIN \
    --mount "type=bind,src=$workspace,dst=/workspace,readonly" -w /workspace \
    -e PYTHONPATH=/workspace -e NFT_BINARY=/usr/sbin/nft "$image" \
    sh -ec 'command -v nft >/dev/null && python3 scripts/p4_real_kernel_runtime_driver.py && python3 scripts/p4_backend_restart_runtime.py'
}

if ip netns add "$namespace" 2>/dev/null; then
  ip netns delete "$namespace"
  run_netns
elif command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  run_container docker
elif command -v podman >/dev/null 2>&1 && podman info >/dev/null 2>&1; then
  run_container podman
else
  echo "SKIP: cannot create ip netns and no accessible rootful Docker/Podman is available" >&2
  exit 77
fi

if host_secmon_present; then
  echo "FAIL: host inet secmon appeared during isolated test" >&2
  exit 1
fi
echo "P4_HOST_ISOLATION_PASS"
