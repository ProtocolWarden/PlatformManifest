#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 ProtocolWarden
#
# bootstrap-boundary-secrets.sh — set (or rotate) the
# REPOGRAPH_BOUNDARY_ARTIFACT_B64 Actions secret across every public repo
# that runs the custodian-audit workflow.
#
# This is the safe path for personal-account operators: GitHub user
# accounts have NO org-level Actions secrets, so the same secret must be
# set per-repo. This script makes that a single command, for both initial
# bootstrap and rotation (re-run after the boundary artifact changes).
#
# The secret is the base64-encoded CONTENT of the boundary disclosure
# artifact. The custodian-audit workflow decodes it to a temp file on the
# runner and exports REPOGRAPH_BOUNDARY_ARTIFACT_FILE for custodian.
# (The older approach — a *_FILE secret holding a path/URL — cannot
# resolve on a CI runner and is retired.)
#
# Usage:
#   ./bootstrap-boundary-secrets.sh \
#       --owner <your-github-account> \
#       --artifact <path/to/boundary_disclosure_artifact.json> \
#       [--repos-file consumer-repos.txt] [--dry-run]
#
# Requirements:
#   - gh (GitHub CLI) authenticated as the repo owner, with `repo` scope
#   - base64 (coreutils)
#
# What the script does NOT do:
#   - It does not generate the artifact (the private-manifest exporter does)
#   - It does not commit anything (only sets remote Actions secrets)

set -euo pipefail

SECRET_NAME="REPOGRAPH_BOUNDARY_ARTIFACT_B64"

# Default consumer-repo list: every public platform repo with a
# custodian-audit workflow. Override with --repos-file.
DEFAULT_REPOS=(
  ContextLifecycle
  CoreRunner
  CritiqueExecutor
  Custodian
  CxRP
  DAGExecutor
  OperationsCenter
  OperatorConsole
  PlatformDeployment
  PlatformManifest
  ProtocolWarden
  ProtocolWarden.github.io
  RepoGraph
  RxP
  SourceRegistry
  SwitchBoard
  SyncMechanism
  TeamExecutor
  Warehouse
)

usage() {
  cat <<EOF
Usage: $0 --owner <github-owner> --artifact <path> [options]

Required:
  --owner <name>         GitHub user that owns the repos
  --artifact <path>      Path to boundary_disclosure_artifact.json
                         (its base64 content becomes the secret value)

Optional:
  --repos-file <path>    File with one consumer repo name per line.
                         Default: the platform list baked into this script
                         (${#DEFAULT_REPOS[@]} repos).
  --dry-run              Print what would be set; do not call gh.
  -h, --help             Show this help.
EOF
}

OWNER=""
ARTIFACT=""
REPOS_FILE=""
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --owner)      OWNER="$2"; shift 2 ;;
    --artifact)   ARTIFACT="$2"; shift 2 ;;
    --repos-file) REPOS_FILE="$2"; shift 2 ;;
    --dry-run)    DRY_RUN=1; shift ;;
    -h|--help)    usage; exit 0 ;;
    *)            echo "Unknown arg: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ -z "$OWNER" || -z "$ARTIFACT" ]]; then
  echo "ERROR: --owner and --artifact are required." >&2
  usage >&2
  exit 2
fi

if [[ ! -s "$ARTIFACT" ]]; then
  echo "ERROR: artifact file '$ARTIFACT' is missing or empty." >&2
  exit 2
fi

# Sanity: the artifact must be valid JSON before it is fanned out.
if command -v python3 >/dev/null 2>&1; then
  python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$ARTIFACT" || {
    echo "ERROR: '$ARTIFACT' is not valid JSON." >&2
    exit 2
  }
fi

# Load the consumer repo list.
if [[ -n "$REPOS_FILE" ]]; then
  mapfile -t REPOS < <(grep -v '^[[:space:]]*\(#\|$\)' "$REPOS_FILE")
else
  REPOS=("${DEFAULT_REPOS[@]}")
fi

B64="$(base64 -w0 "$ARTIFACT")"

echo "Owner:           $OWNER"
echo "Artifact:        $ARTIFACT ($(wc -c < "$ARTIFACT") bytes)"
echo "Secret:          $SECRET_NAME"
echo "Consumer repos:  ${#REPOS[@]}"
echo

failures=()
for repo in "${REPOS[@]}"; do
  echo "=== $repo ==="
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "  would set $SECRET_NAME (${#B64} chars)"
    continue
  fi
  if ! printf '%s' "$B64" | gh secret set "$SECRET_NAME" \
       --repo "${OWNER}/${repo}" 2>&1; then
    failures+=("$repo")
    continue
  fi
done

echo
if [[ ${#failures[@]} -gt 0 ]]; then
  echo "FAILURES: ${#failures[@]}"
  for f in "${failures[@]}"; do echo "  - $f"; done
  exit 1
fi
echo "All ${#REPOS[@]} repos configured."
