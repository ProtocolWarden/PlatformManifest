#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 ProtocolWarden
#
# bootstrap-boundary-secrets.sh — set REPOGRAPH_BOUNDARY_ARTIFACT_FILE and
# PRIVATEMANIFEST_READ_TOKEN secrets across every public repo that runs the
# custodian-audit workflow.
#
# This script is the safe path for personal-account operators (no GitHub
# organization, so no org-level secrets). It accepts the PAT via a file
# whose path you provide, sets both secrets in each listed repo, and shreds
# the local PAT file when done.
#
# Usage:
#   1. Generate a fine-grained PAT scoped read-only to your PrivateManifest
#      (Settings → Developer settings → Personal access tokens → Fine-grained)
#   2. Write it to a temp file with NO trailing newline:
#        printf '%s' 'github_pat_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx' > /tmp/pat
#      Or interactively (no shell history record):
#        read -s -p 'PAT: ' p && printf '%s' "$p" > /tmp/pat && unset p
#   3. Run this script:
#        ./bootstrap-boundary-secrets.sh \
#            --owner <your-github-account> \
#            --private-repo <your-PrivateManifest-name> \
#            --token-file /tmp/pat \
#            --repos-file consumer-repos.txt
#      Or with the default repo list embedded below:
#        ./bootstrap-boundary-secrets.sh --owner <owner> --token-file /tmp/pat
#   4. The script shreds the token file on exit (success OR failure). If
#      you cancel mid-run, manually run: shred -u /tmp/pat
#
# Requirements:
#   - gh (GitHub CLI) authenticated as the repo owner
#   - shred (GNU coreutils — present on most Linux distros)
#
# What the script does NOT do:
#   - It does not generate the PAT (you do that in the GitHub UI)
#   - It does not store the PAT anywhere persistent
#   - It does not commit changes to any repo (only sets remote secrets)

set -euo pipefail

# Defaults — override with --private-repo / --branch / --artifact-path
PRIVATE_REPO_DEFAULT="PrivateManifest"
BRANCH_DEFAULT="main"
ARTIFACT_PATH_DEFAULT="boundary/boundary_disclosure_artifact.json"

# Default consumer-repo list (every repo in the platform that runs
# custodian-audit.yml). Override with --repos-file to use your own list.
DEFAULT_REPOS=(
  CoreRunner
  CritiqueExecutor
  Custodian
  CxRP
  DAGExecutor
  OperationsCenter
  OperatorConsole
  PlatformDeployment
  PlatformManifest
  RxP
  SourceRegistry
  SwitchBoard
  TeamExecutor
)

usage() {
  cat <<EOF
Usage: $0 --owner <github-owner> --token-file <path> [options]

Required:
  --owner <name>             GitHub user or org that owns the repos
  --token-file <path>        File containing the PAT (no trailing newline)

Optional:
  --private-repo <name>      Name of your PrivateManifest repo
                             (default: $PRIVATE_REPO_DEFAULT)
  --branch <name>            Branch to fetch the artifact from
                             (default: $BRANCH_DEFAULT)
  --artifact-path <path>     Path to the artifact within the private repo
                             (default: $ARTIFACT_PATH_DEFAULT)
  --repos-file <path>        File with one consumer repo name per line.
                             If omitted, uses the platform default list
                             baked into this script.
  --dry-run                  Print what would be set; do not call gh.
  --no-shred                 Skip the shred of --token-file at exit.
                             (Default is to shred — use this only if you
                             are sharing the file with another script.)
  -h, --help                 Show this help.
EOF
}

OWNER=""
TOKEN_FILE=""
PRIVATE_REPO="$PRIVATE_REPO_DEFAULT"
BRANCH="$BRANCH_DEFAULT"
ARTIFACT_PATH="$ARTIFACT_PATH_DEFAULT"
REPOS_FILE=""
DRY_RUN=0
NO_SHRED=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --owner)          OWNER="$2"; shift 2 ;;
    --token-file)     TOKEN_FILE="$2"; shift 2 ;;
    --private-repo)   PRIVATE_REPO="$2"; shift 2 ;;
    --branch)         BRANCH="$2"; shift 2 ;;
    --artifact-path)  ARTIFACT_PATH="$2"; shift 2 ;;
    --repos-file)     REPOS_FILE="$2"; shift 2 ;;
    --dry-run)        DRY_RUN=1; shift ;;
    --no-shred)       NO_SHRED=1; shift ;;
    -h|--help)        usage; exit 0 ;;
    *)                echo "Unknown arg: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ -z "$OWNER" || -z "$TOKEN_FILE" ]]; then
  echo "ERROR: --owner and --token-file are required." >&2
  usage >&2
  exit 2
fi

if [[ ! -s "$TOKEN_FILE" ]]; then
  echo "ERROR: token file '$TOKEN_FILE' is missing or empty." >&2
  exit 2
fi

# Always shred the token file unless explicitly disabled — even on failure.
cleanup() {
  if [[ "$NO_SHRED" -eq 0 ]]; then
    if [[ -f "$TOKEN_FILE" ]]; then
      shred -u "$TOKEN_FILE" 2>/dev/null && echo "Token file shredded." || \
        echo "WARNING: could not shred '$TOKEN_FILE'; remove it manually."
    fi
  fi
}
trap cleanup EXIT

# Load the consumer repo list.
if [[ -n "$REPOS_FILE" ]]; then
  mapfile -t REPOS < <(grep -v '^[[:space:]]*\(#\|$\)' "$REPOS_FILE")
else
  REPOS=("${DEFAULT_REPOS[@]}")
fi

BOUNDARY_URL="https://raw.githubusercontent.com/${OWNER}/${PRIVATE_REPO}/${BRANCH}/${ARTIFACT_PATH}"

echo "Owner:           $OWNER"
echo "Private repo:    $PRIVATE_REPO ($BRANCH)"
echo "Artifact URL:    $BOUNDARY_URL"
echo "Consumer repos:  ${#REPOS[@]}"
echo

failures=()
for repo in "${REPOS[@]}"; do
  echo "=== $repo ==="
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "  would set PRIVATEMANIFEST_READ_TOKEN (from $TOKEN_FILE)"
    echo "  would set REPOGRAPH_BOUNDARY_ARTIFACT_FILE=$BOUNDARY_URL"
    continue
  fi
  if ! gh secret set PRIVATEMANIFEST_READ_TOKEN \
       --repo "${OWNER}/${repo}" < "$TOKEN_FILE" 2>&1; then
    failures+=("$repo (PAT secret)")
    continue
  fi
  if ! gh secret set REPOGRAPH_BOUNDARY_ARTIFACT_FILE \
       --repo "${OWNER}/${repo}" --body "$BOUNDARY_URL" 2>&1; then
    failures+=("$repo (URL secret)")
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
