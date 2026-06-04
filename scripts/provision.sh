#!/usr/bin/env bash
# provision.sh — one entrypoint to provision a machine from a fresh
# PlatformManifest clone.
#
# Runs the steps in the only order that works:
#   1. clone-repos.sh       — clone the ecosystem repos (CL + RG must land first;
#                             provision-machine.sh hard-requires them)
#   2. provision-machine.sh — venvs, CL_HOME wiring, RepoGraph registry, hooks,
#                             smoke test
#
# Idempotent: safe to re-run. Flags pass through to both child scripts.
#
# Usage:
#   provision.sh [--with-private] [--force-hooks]
#
#   --with-private   clone + register private-manifest repos and install their
#                    hooks (requires the private-manifest repo already cloned)
#   --force-hooks    overwrite existing hooks instead of skipping
#
# NOT handled here (manual, one-time, needs a GitHub PAT):
#   bootstrap-boundary-secrets.sh — sets CI secrets on public repos. Run it
#   separately once per account; see its --help.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

WITH_PRIVATE=false
PASSTHRU=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-private) WITH_PRIVATE=true; PASSTHRU+=("--with-private"); shift ;;
    --force-hooks)  PASSTHRU+=("--force-hooks"); shift ;;
    *) echo "provision.sh: unknown argument: $1" >&2; exit 2 ;;
  esac
done

echo "▶ provision (clone → machine setup)"
echo ""

# clone-repos.sh only understands --with-private.
CLONE_ARGS=()
[[ "$WITH_PRIVATE" == true ]] && CLONE_ARGS+=("--with-private")
bash "$SCRIPT_DIR/clone-repos.sh" "${CLONE_ARGS[@]}"

echo ""
bash "$SCRIPT_DIR/provision-machine.sh" "${PASSTHRU[@]}"

echo ""
echo "✓ provision complete"
echo "  Next (manual, once per account): scripts/bootstrap-boundary-secrets.sh --help"
