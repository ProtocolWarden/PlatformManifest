#!/usr/bin/env bash
# provision-machine.sh — one-shot machine setup for the ProtocolWarden ecosystem.
#
# Idempotent: safe to re-run on an already-provisioned machine.
#
# What it does:
#   1. Build/verify ContextLifecycle and RepoGraph Python venvs
#   2. Wire CL_HOME + PATH into ~/.bashrc (once, idempotent)
#   3. Register PlatformManifest (+ PrivateManifest if present) in the RepoGraph
#      per-machine registry
#   4. Install ContextLifecycle adapter hooks into repos that are missing them
#   5. Smoke-test: verify `cl session start` resolves correctly from key repos
#
# Usage:
#   provision-machine.sh [--with-private] [--force-hooks]
#
#   --with-private   also register PrivateManifest + install hooks in private repos
#   --force-hooks    overwrite existing hooks (default: skip repos that already have them)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PM_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
GITHUB_DIR="$(cd "$PM_DIR/.." && pwd)"

WITH_PRIVATE=false
FORCE_HOOKS=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-private) WITH_PRIVATE=true; shift ;;
    --force-hooks)  FORCE_HOOKS=true;  shift ;;
    *) echo "provision-machine.sh: unknown argument: $1" >&2; exit 2 ;;
  esac
done

CL_DIR="$GITHUB_DIR/ContextLifecycle"
RG_DIR="$GITHUB_DIR/RepoGraph"

_require_repo() {
  local dir="$1" name="$2"
  if [[ ! -d "$dir/.git" ]]; then
    echo "ERROR: $name not found at $dir" >&2
    echo "  Run scripts/clone-repos.sh first." >&2
    exit 1
  fi
}

# ── 1. Verify key repos present ──────────────────────────────────────────────
echo "▶ provision-machine"
echo "  github-dir: $GITHUB_DIR"
echo ""

echo "▶ [1/5] Checking required repos"
_require_repo "$CL_DIR"  "ContextLifecycle"
_require_repo "$RG_DIR"  "RepoGraph"
echo "  ✓ ContextLifecycle, RepoGraph present"

# ── 2. Build venvs ───────────────────────────────────────────────────────────
echo ""
echo "▶ [2/5] Python venvs"

_ensure_venv() {
  local dir="$1" name="$2"
  local venv="$dir/.venv"
  if [[ ! -x "$venv/bin/python" ]]; then
    echo "  building $name venv..."
    python3 -m venv "$venv"
    "$venv/bin/pip" install --quiet --upgrade pip
    "$venv/bin/pip" install --quiet -e "$dir"
    echo "  ✓ $name venv built"
  else
    echo "  ✓ $name venv OK"
  fi
}

_ensure_venv "$CL_DIR" "ContextLifecycle"
_ensure_venv "$RG_DIR" "RepoGraph"

# ── 3. Shell profile: CL_HOME + PATH ─────────────────────────────────────────
echo ""
echo "▶ [3/5] Shell profile (~/.bashrc)"

BASHRC="$HOME/.bashrc"
MARKER="# ContextLifecycle: point CL_HOME at the CL repo so shims and loops find \`cl\`"
if grep -qF "$MARKER" "$BASHRC" 2>/dev/null; then
  echo "  ✓ CL_HOME already wired in ~/.bashrc"
else
  cat >> "$BASHRC" << SHELL

$MARKER
export CL_HOME="$CL_DIR"
export PATH="\$CL_HOME/bin:\$PATH"
SHELL
  echo "  ✓ Added CL_HOME + PATH to ~/.bashrc"
  echo "    (run: source ~/.bashrc  or open a new shell)"
fi

# Make cl available in this session too
export CL_HOME="$CL_DIR"
export PATH="$CL_HOME/bin:$PATH"

# ── 4. RepoGraph registry ─────────────────────────────────────────────────────
echo ""
echo "▶ [4/5] RepoGraph registry"

RG_BIN="$RG_DIR/.venv/bin/repograph"
CL_BIN="$CL_HOME/bin/cl"

_register_manifest() {
  local path="$1"
  local name
  name="$(basename "$path")"
  if "$RG_BIN" manifest list 2>/dev/null | grep -qF "$path"; then
    echo "  ✓ $name already registered"
  else
    "$RG_BIN" manifest add "$path"
    echo "  ✓ $name registered"
  fi
}

_register_manifest "$PM_DIR"

if [[ "$WITH_PRIVATE" == true ]]; then
  PRIVM_DIR="$GITHUB_DIR/PrivateManifest"
  if [[ -d "$PRIVM_DIR/.git" ]]; then
    _register_manifest "$PRIVM_DIR"
  else
    echo "  skip: PrivateManifest not cloned (pass --with-private after cloning it)"
  fi
elif [[ -d "$GITHUB_DIR/PrivateManifest/.git" ]]; then
  # Auto-register PrivateManifest if it's already cloned — no need for flag
  _register_manifest "$GITHUB_DIR/PrivateManifest"
fi

# ── 5. Adapter hooks ──────────────────────────────────────────────────────────
echo ""
echo "▶ [5/5] ContextLifecycle adapter hooks"

INSTALL_SH="$CL_DIR/adapters/install.sh"

# Repos that need the FULL canonical ContextGuard adapter (not the executor shim).
# Skip repos that already have hooks unless --force-hooks was passed.
FULL_ADAPTER_REPOS=("PlatformManifest")  # OC has custom patched hooks — skip by default

# Repos that need the 9-LINE EXECUTOR SHIM (delegates enforcement to CL).
SHIM_REPOS=("DAGExecutor")  # TE + CE already have it; OC/VF have custom hooks

_install_full_adapter() {
  local name="$1"
  local repo_dir="$GITHUB_DIR/$name"
  [[ -d "$repo_dir/.git" ]] || { echo "  skip $name (not cloned)"; return; }
  if [[ -f "$repo_dir/.claude/hooks/pre_tool_use.sh" && "$FORCE_HOOKS" != true ]]; then
    echo "  ✓ $name (full adapter already present — use --force-hooks to re-sync)"
    return
  fi
  bash "$INSTALL_SH" "$repo_dir" --cli claude
  echo "  ✓ $name full adapter installed"
}

_install_shim() {
  local name="$1"
  local repo_dir="$GITHUB_DIR/$name"
  [[ -d "$repo_dir/.git" ]] || { echo "  skip $name (not cloned)"; return; }
  if [[ -f "$repo_dir/.claude/hooks/pre_tool_use.sh" && "$FORCE_HOOKS" != true ]]; then
    echo "  ✓ $name (shim already present — use --force-hooks to re-sync)"
    return
  fi
  mkdir -p "$repo_dir/.claude/hooks"
  # 9-line delegation shim: resolves cl via CL_HOME or PATH, delegates to CL's
  # own enforcement (require_anchor_env, workspace capsule checks, etc.)
  cat > "$repo_dir/.claude/hooks/pre_tool_use.sh" << 'SHIM'
#!/usr/bin/env bash
set -euo pipefail
CL_BIN="${CL_HOME:+$CL_HOME/bin/cl}"
CL_BIN="${CL_BIN:-$(command -v cl 2>/dev/null || true)}"
if [[ -z "$CL_BIN" || ! -x "$CL_BIN" ]]; then
  echo "ContextLifecycle: cl not found. Set CL_HOME to the CL repo root or install cl on PATH." >&2
  exit 1
fi
exec "$CL_BIN" hook pre_tool_use "$@"
SHIM
  cat > "$repo_dir/.claude/hooks/stop.sh" << 'SHIM'
#!/usr/bin/env bash
set -euo pipefail
CL_BIN="${CL_HOME:+$CL_HOME/bin/cl}"
CL_BIN="${CL_BIN:-$(command -v cl 2>/dev/null || true)}"
[[ -z "$CL_BIN" || ! -x "$CL_BIN" ]] && exit 0
exec "$CL_BIN" hook stop "$@"
SHIM
  chmod +x "$repo_dir/.claude/hooks/"*.sh
  # Wire hooks into settings.json (same merge logic as install.sh)
  python3 - "$repo_dir/.claude/settings.json" "$CL_DIR/adapters/claude/settings.json" <<'PY'
import json, sys, pathlib
target, canonical = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
base = json.loads(target.read_text(encoding="utf-8")) if target.exists() else {}
base["hooks"] = json.loads(canonical.read_text(encoding="utf-8"))["hooks"]
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(json.dumps(base, indent=2) + "\n", encoding="utf-8")
PY
  echo "  ✓ $name shim installed"
}

for repo in "${FULL_ADAPTER_REPOS[@]}"; do _install_full_adapter "$repo"; done
for repo in "${SHIM_REPOS[@]}";         do _install_shim "$repo"; done

if [[ "$WITH_PRIVATE" == true ]]; then
  # Private repos that need the full adapter (already have custom hooks — skip by default)
  for repo in VideoFoundry SyncControl; do
    dir="$GITHUB_DIR/$repo"
    [[ -d "$dir/.git" ]] || continue
    if [[ -f "$dir/.claude/hooks/pre_tool_use.sh" && "$FORCE_HOOKS" != true ]]; then
      echo "  ✓ $repo (hooks already present)"
    else
      _install_full_adapter "$repo"
    fi
  done
fi

# ── Smoke test ────────────────────────────────────────────────────────────────
echo ""
echo "▶ Smoke test: cl session start"

declare -A EXPECTED_ANCHORS=(
  ["OperationsCenter"]="PlatformManifest"
  ["PlatformManifest"]="PlatformManifest"
)
if [[ -d "$GITHUB_DIR/PrivateManifest/.git" ]]; then
  EXPECTED_ANCHORS["VideoFoundry"]="PrivateManifest"
  EXPECTED_ANCHORS["SyncControl"]="PrivateManifest"
fi

SMOKE_PASS=true
for repo in "${!EXPECTED_ANCHORS[@]}"; do
  expected="${EXPECTED_ANCHORS[$repo]}"
  dir="$GITHUB_DIR/$repo"
  [[ -d "$dir/.git" ]] || continue
  got=$(cd "$dir" && "$CL_BIN" session start 2>/dev/null | grep CL_ANCHOR | sed 's/.*CL_ANCHOR="\(.*\)"/\1/' | xargs basename 2>/dev/null || echo "ERROR")
  if [[ "$got" == "$expected" ]]; then
    printf "  ✓ %-20s → %s\n" "$repo" "$got"
  else
    printf "  ✗ %-20s → %s (expected %s)\n" "$repo" "$got" "$expected"
    SMOKE_PASS=false
  fi
done

echo ""
if [[ "$SMOKE_PASS" == true ]]; then
  echo "✓ provision-machine complete — ecosystem ready"
else
  echo "✗ smoke test failures above — check RepoGraph registry and manifest YAMLs" >&2
  exit 1
fi
