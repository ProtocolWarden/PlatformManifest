#!/usr/bin/env bash
# clone-repos.sh — clone all manifest repos to this machine.
#
# Reads github_url + canonical_name from platform_manifest.yaml (and
# optionally private_manifest.yaml) and clones any that are not already
# present under GITHUB_DIR. Skips repos that already exist. Idempotent.
#
# Usage:
#   clone-repos.sh [--with-private] [--github-dir <path>]
#
# Defaults:
#   GITHUB_DIR   — parent of the PlatformManifest repo root (i.e. ~/Documents/GitHub)
#   --with-private  also clone repos declared in the private manifest

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PM_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
GITHUB_DIR="$(cd "$PM_DIR/.." && pwd)"

# Role-based private-manifest resolver — shared lib (single source of truth).
# shellcheck source=lib/private-manifest.sh
source "$SCRIPT_DIR/lib/private-manifest.sh"

WITH_PRIVATE=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-private) WITH_PRIVATE=true; shift ;;
    --github-dir)   GITHUB_DIR="$2"; shift 2 ;;
    *) echo "clone-repos.sh: unknown argument: $1" >&2; exit 2 ;;
  esac
done

# Convert HTTPS GitHub URL → SSH remote
# https://github.com/ProtocolWarden/Foo → git@github.com:ProtocolWarden/Foo.git
_to_ssh() {
  echo "$1" | sed 's|https://github.com/|git@github.com:|' | sed 's|$|.git|'
}

_clone_from_yaml() {
  local yaml_file="$1"
  [[ -f "$yaml_file" ]] || { echo "  skip: $yaml_file not found"; return; }

  # Extract canonical_name + github_url pairs using Python (already required for venvs)
  python3 - "$yaml_file" <<'PY'
import sys, pathlib
try:
    import yaml
except ImportError:
    # Minimal YAML parser for the simple repo-list structure we need
    import re
    text = pathlib.Path(sys.argv[1]).read_text()
    pairs = re.findall(r'canonical_name:\s*(\S+).*?github_url:\s*(\S+)', text, re.DOTALL)
    for name, url in pairs:
        print(f"{name}\t{url}")
    sys.exit(0)

data = yaml.safe_load(pathlib.Path(sys.argv[1]).read_text())
repos = data.get("repos", {})
if isinstance(repos, dict):
    for _key, fields in repos.items():
        if isinstance(fields, dict):
            name = fields.get("canonical_name")
            url  = fields.get("github_url")
            if name and url:
                print(f"{name}\t{url}")
elif isinstance(repos, list):
    for item in repos:
        if isinstance(item, dict):
            name = item.get("canonical_name") or item.get("name")
            url  = item.get("github_url")
            if name and url:
                print(f"{name}\t{url}")
PY
}

_process_yaml() {
  local yaml_file="$1"
  local cloned=0 skipped=0 failed=0

  while IFS=$'\t' read -r canonical_name github_url; do
    [[ -z "$canonical_name" || -z "$github_url" ]] && continue
    dest="$GITHUB_DIR/$canonical_name"
    if [[ -d "$dest/.git" ]]; then
      printf "  %-35s already present\n" "$canonical_name"
      (( skipped++ )) || true
    else
      ssh_url="$(_to_ssh "$github_url")"
      printf "  %-35s cloning %s\n" "$canonical_name" "$ssh_url"
      if git clone "$ssh_url" "$dest" --quiet 2>&1; then
        (( cloned++ )) || true
      else
        echo "    WARN: clone failed for $canonical_name — skipping" >&2
        (( failed++ )) || true
      fi
    fi
  done < <(_clone_from_yaml "$yaml_file")

  echo "  cloned=$cloned  skipped=$skipped  failed=$failed"
}

echo "▶ clone-repos"
echo "  github-dir: $GITHUB_DIR"
echo ""

echo "▶ Public repos (PlatformManifest)"
_process_yaml "$PM_DIR/src/platform_manifest/data/platform_manifest.yaml"

if [[ "$WITH_PRIVATE" == true ]]; then
  PRIVM_DIR="$(_discover_private_manifest_dir || true)"
  echo ""
  echo "▶ Private repos (private manifest)"
  if [[ -n "$PRIVM_DIR" && -d "$PRIVM_DIR" ]]; then
    # Discover manifest YAMLs dynamically — no private names hardcoded here.
    while IFS= read -r yaml_file; do
      _process_yaml "$yaml_file"
    done < <(find "$PRIVM_DIR/manifests" -name "*.yaml" 2>/dev/null | sort)
  else
    echo "  skip: no private-manifest repo found under $GITHUB_DIR"
    echo "  Hint: clone your private-manifest repo first (or set PRIVATE_MANIFEST_DIR), then re-run with --with-private"
  fi
fi

echo ""
echo "✓ Done"
