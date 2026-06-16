#!/usr/bin/env bash
# provision-machine.sh — one-shot machine setup for the ProtocolWarden ecosystem.
#
# Idempotent: safe to re-run on an already-provisioned machine.
#
# What it does:
#   1. Build/verify ContextLifecycle, RepoGraph and Custodian Python venvs, and
#      refresh the local (editable) Custodian into every managed repo venv that
#      carries a custodian-multi — so the pre-push audit gate runs current
#      detectors (e.g. CAP1) instead of a stale pinned copy
#   2. Wire CL_HOME + PATH into ~/.bashrc (once, idempotent)
#   3. Register PlatformManifest (+ the private manifest if present) in the
#      RepoGraph per-machine registry
#   4. Install ContextLifecycle adapter hooks into repos that are missing them
#   5. Smoke-test: verify `cl session start` resolves correctly from key repos
#
# Usage:
#   provision-machine.sh [--with-private] [--force-hooks]
#
#   --with-private   also register the private manifest + install hooks in private repos
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
CUST_DIR="$GITHUB_DIR/Custodian"

# Role-based private-manifest resolver — shared lib (single source of truth).
# shellcheck source=lib/private-manifest.sh
source "$SCRIPT_DIR/lib/private-manifest.sh"

PRIVM_DIR="$(_discover_private_manifest_dir || true)"

# Extract canonical_name + github_url pairs from a manifest YAML.
# Output: tab-separated "canonical_name\tgithub_url" lines.
_extract_names_from_yaml() {
  local yaml_file="$1"
  [[ -f "$yaml_file" ]] || return 0
  python3 - "$yaml_file" <<'PY'
import sys, pathlib, re
try:
    import yaml
    data = yaml.safe_load(pathlib.Path(sys.argv[1]).read_text())
    repos = data.get("repos", {})
    if isinstance(repos, dict):
        for _k, f in repos.items():
            if isinstance(f, dict):
                name = f.get("canonical_name"); url = f.get("github_url", "")
                if name: print(f"{name}\t{url}")
    elif isinstance(repos, list):
        for item in repos:
            if isinstance(item, dict):
                name = item.get("canonical_name") or item.get("name"); url = item.get("github_url", "")
                if name: print(f"{name}\t{url}")
except ImportError:
    text = pathlib.Path(sys.argv[1]).read_text()
    for name, url in re.findall(r'canonical_name:\s*(\S+).*?github_url:\s*(\S+)', text, re.DOTALL):
        print(f"{name}\t{url}")
PY
}

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
_require_repo "$CUST_DIR" "Custodian"
echo "  ✓ ContextLifecycle, RepoGraph, Custodian present"

# Update the tool repos so re-provision picks up shipped behavior (a stale CL
# checkout means stale `cl` semantics on this host — e.g. no session auto-GC).
# Best-effort: skip with a note when dirty / on a feature branch / offline —
# never fail provisioning over it.
_update_repo() {
  local dir="$1" name="$2"
  local branch
  branch="$(git -C "$dir" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")"
  if [[ "$branch" != "main" && "$branch" != "master" ]]; then
    echo "  – $name: on '$branch' (not default branch) — skipping pull"
    return 0
  fi
  if [[ -n "$(git -C "$dir" status --porcelain 2>/dev/null)" ]]; then
    echo "  – $name: working tree dirty — skipping pull"
    return 0
  fi
  if git -C "$dir" pull --ff-only --quiet 2>/dev/null; then
    echo "  ✓ $name up to date ($(git -C "$dir" rev-parse --short HEAD))"
  else
    echo "  – $name: pull failed (offline or non-ff) — continuing with local HEAD"
  fi
}

_update_repo "$CL_DIR" "ContextLifecycle"
_update_repo "$RG_DIR" "RepoGraph"
_update_repo "$CUST_DIR" "Custodian"

# ── 2. Build venvs ───────────────────────────────────────────────────────────
echo ""
echo "▶ [2/5] Python venvs"

# Run pip inside a venv as `python -m pip`, bootstrapping pip first when it's
# absent. uv-created venvs (e.g. Custodian's, made with `uv venv`) ship WITHOUT
# pip, so a bare `$venv/bin/pip` would not exist — ensurepip (stdlib) installs it.
_venv_pip() {
  local venv="$1"; shift
  if [[ ! -x "$venv/bin/pip" ]]; then
    "$venv/bin/python" -m ensurepip --upgrade >/dev/null 2>&1 || true
  fi
  "$venv/bin/python" -m pip "$@"
}

_ensure_venv() {
  local dir="$1" name="$2"
  local venv="$dir/.venv"
  if [[ ! -x "$venv/bin/python" ]]; then
    echo "  building $name venv..."
    python3 -m venv "$venv"
  fi
  # Always (re)install editable so dependency changes from a git pull are
  # picked up on re-provision. pip is a near-no-op when nothing changed.
  _venv_pip "$venv" install --quiet --upgrade pip
  _venv_pip "$venv" install --quiet -e "$dir"
  echo "  ✓ $name venv ready"
}

_ensure_venv "$CL_DIR" "ContextLifecycle"
_ensure_venv "$RG_DIR" "RepoGraph"
# Custodian's own venv is the canonical custodian-multi — the last-resort
# candidate the pre-push gate falls through to (Custodian/.venv/bin/custodian-multi).
_ensure_venv "$CUST_DIR" "Custodian"

# Refresh the local (editable) Custodian INTO every other managed repo venv that
# already carries a custodian-multi. The pre-push audit gate resolves
# custodian-multi from the repo's OWN .venv before the Custodian sibling venv, so
# a stale per-repo copy (e.g. an old pinned SHA) silently disables newer detectors
# like CAP1. Editable-install tracks local Custodian main and is picked up on every
# re-provision — same idempotent contract as _ensure_venv. Only repos that already
# have custodian-multi are touched (we don't add the dep to venvs that don't want it).
_refresh_custodian_in() {
  local dir="$1" name="$2"
  local venv="$dir/.venv"
  [[ -x "$venv/bin/custodian-multi" ]] || return 0
  if _venv_pip "$venv" install --quiet -e "$CUST_DIR"; then
    echo "  ✓ $name: custodian refreshed (editable → local Custodian)"
  else
    echo "  – $name: custodian refresh failed — continuing (pre-push falls back to Custodian/.venv)"
  fi
}
for repo_dir in "$GITHUB_DIR"/*/; do
  [[ -d "$repo_dir/.git" ]] || continue
  [[ "$(cd "$repo_dir" && pwd)" == "$CUST_DIR" ]] && continue   # Custodian itself handled above
  _refresh_custodian_in "$repo_dir" "$(basename "$repo_dir")"
done

# ── 3. Shell profile + Claude Code env ───────────────────────────────────────
echo ""
echo "▶ [3/5] Shell profile (~/.bashrc) + ~/.claude/settings.json"

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

# Wire CL_HOME into ~/.claude/settings.json so Claude Code's process (and its
# hook subprocesses) can find `cl` without sourcing ~/.bashrc. Idempotent.
CLAUDE_SETTINGS="$HOME/.claude/settings.json"
python3 - "$CLAUDE_SETTINGS" "$CL_DIR" <<'PY'
import json, sys, pathlib
settings_path = pathlib.Path(sys.argv[1])
cl_home = sys.argv[2]
base = json.loads(settings_path.read_text()) if settings_path.exists() else {}
env = base.setdefault("env", {})
if env.get("CL_HOME") == cl_home:
    print("  ✓ CL_HOME already in ~/.claude/settings.json")
else:
    env["CL_HOME"] = cl_home
    settings_path.write_text(json.dumps(base, indent=2) + "\n")
    print("  ✓ Added CL_HOME to ~/.claude/settings.json")
PY

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
  if [[ -n "$PRIVM_DIR" && -d "$PRIVM_DIR/.git" ]]; then
    _register_manifest "$PRIVM_DIR"
  else
    echo "  skip: no private-manifest repo found (clone it, or set PRIVATE_MANIFEST_DIR, then pass --with-private)"
  fi
elif [[ -n "$PRIVM_DIR" && -d "$PRIVM_DIR/.git" ]]; then
  # Auto-register the private manifest if it's already cloned — no need for flag
  _register_manifest "$PRIVM_DIR"
fi

# ── 5. Adapter hooks ──────────────────────────────────────────────────────────
echo ""
echo "▶ [5/5] ContextLifecycle adapter hooks"

INSTALL_SH="$CL_DIR/adapters/install.sh"

# Repos that need the FULL canonical ContextGuard adapter (not the executor shim).
# Skip repos that already have hooks unless --force-hooks was passed.
FULL_ADAPTER_REPOS=("PlatformManifest")

# Repos that get the executor shim (pre_tool_use delegates to CL) + Gen 2 stop.sh.
SHIM_REPOS=("DAGExecutor")

# Repos whose ContextGuard hooks are committed in-repo (not installed here).
# Listed so the hook-health check below can verify they're actually present —
# catches drift if a committed hook is removed or broken.
COMMITTED_HOOK_REPOS=("OperationsCenter" "OperatorConsole" "TeamExecutor" "CritiqueExecutor")

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
  # pre_tool_use: delegation shim — resolves cl via CL_HOME or PATH, delegates to CL.
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
  # stop.sh: Gen 2 ContextGuard — CL_ANCHOR-based checkpoint + capsule checks.
  cat > "$repo_dir/.claude/hooks/stop.sh" << 'SHIM'
#!/usr/bin/env bash
# ContextGuard — Claude Code Stop adapter
# Implements: on_stop
#
# Runs when the Claude Code session ends.
# Warns if no checkpoint was written this session.
# Warns if active capsule was not updated.
# Blocks termination if loop.checkpoint_on_stop: true and no checkpoint written.

set -euo pipefail

# --- Manifest anchor: cognition ALWAYS anchors at a manifest, never CWD ---
# CL_ANCHOR is exported by `cl session start <manifest>`. On the Stop hook we
# skip gracefully when it is absent (no anchor → nothing to checkpoint here)
# rather than block the session from ending; enforcement lives in pre_tool_use.
if [[ -z "${CL_ANCHOR:-}" ]]; then
  echo "ContextGuard: CL_ANCHOR not set — no manifest anchor, skipping stop checks." >&2
  exit 0
fi
REPO_ROOT="${CL_ANCHOR}"
CONFIG_FILE="${REPO_ROOT}/.context/config.yaml"

# --- Session marker (written by pre_tool_use.sh on first tool call this session) ---
_SESSION_HASH="$(echo "$REPO_ROOT" | cksum | cut -d' ' -f1)"
SESSION_MARKER="/tmp/clp_session_${_SESSION_HASH}"

# --- Load config ---
CHECKPOINT_ON_STOP=true
CAPSULE_PATH=".context/active/"
CHECKPOINT_PATH=".context/checkpoints/"

if [[ -f "${CONFIG_FILE}" ]] && command -v python3 &>/dev/null; then
  CHECKPOINT_ON_STOP=$(python3 -c "
try:
    import yaml
    with open('${CONFIG_FILE}') as f:
        c = yaml.safe_load(f)
    print(str(c.get('loop', {}).get('checkpoint_on_stop', True)).lower())
except Exception:
    print('true')
" 2>/dev/null || echo "true")

  CAPSULE_PATH=$(python3 -c "
try:
    import yaml
    with open('${CONFIG_FILE}') as f:
        c = yaml.safe_load(f)
    print(c.get('guard', {}).get('capsule_path', '.context/active/'))
except Exception:
    print('.context/active/')
" 2>/dev/null || echo ".context/active/")

  CHECKPOINT_PATH=$(python3 -c "
try:
    import yaml
    with open('${CONFIG_FILE}') as f:
        c = yaml.safe_load(f)
    print(c.get('guard', {}).get('checkpoint_path', '.context/checkpoints/'))
except Exception:
    print('.context/checkpoints/')
" 2>/dev/null || echo ".context/checkpoints/")
fi

# --- Helper: warn ---
warn() {
  echo "ContextGuard warning: $1" >&2
}

# --- Check: was a checkpoint written this session? ---
# Uses SESSION_MARKER (created by pre_tool_use.sh on first tool call) as the
# timestamp reference. find -newer detects only checkpoints written after session start.
# Falls back to existence check if the marker is absent (session without tool calls).

CHECKPOINT_DIR="${REPO_ROOT}/${CHECKPOINT_PATH}"
CHECKPOINT_FOUND=false

if [[ -d "$CHECKPOINT_DIR" ]]; then
  if [[ -f "$SESSION_MARKER" ]]; then
    SESSION_CHECKPOINT="$(find "$CHECKPOINT_DIR" -name "*.yaml" -not -name ".gitkeep" -newer "$SESSION_MARKER" | head -1)"
    if [[ -n "$SESSION_CHECKPOINT" ]]; then
      CHECKPOINT_FOUND=true
    fi
  else
    CHECKPOINT_COUNT=$(find "$CHECKPOINT_DIR" -name "*.yaml" -not -name ".gitkeep" | wc -l)
    if [[ "$CHECKPOINT_COUNT" -gt 0 ]]; then
      CHECKPOINT_FOUND=true
    fi
  fi
fi

if [[ "$CHECKPOINT_FOUND" == "false" ]]; then
  if [[ "$CHECKPOINT_ON_STOP" == "true" ]]; then
    echo "ContextGuard: Session ending without a LoopCheckpoint. Write a checkpoint before terminating." >&2
    echo "  Create: .context/checkpoints/<checkpoint-id>.yaml" >&2
    echo "  Template: .context/templates/loop_checkpoint.template.yaml" >&2
    # Non-fatal warn — Claude Code Stop hooks can't hard-block session end in all cases
    # but surfacing this prominently is the enforcement mechanism
  else
    warn "Session ending without a LoopCheckpoint."
  fi
fi

# --- Check: active capsule not updated ---
CAPSULE_DIR="${REPO_ROOT}/${CAPSULE_PATH}"
if [[ -d "$CAPSULE_DIR" ]]; then
  ACTIVE_CAPSULE=$(find "$CAPSULE_DIR" -name "*.yaml" -not -name ".gitkeep" | head -1)
  if [[ -n "$ACTIVE_CAPSULE" ]] && command -v python3 &>/dev/null; then
    CAPSULE_STATUS=$(python3 -c "
try:
    import yaml
    with open('${ACTIVE_CAPSULE}') as f:
        d = yaml.safe_load(f)
    print(d.get('status', 'active'))
except Exception:
    print('active')
" 2>/dev/null || echo "active")

    if [[ "$CAPSULE_STATUS" == "active" ]]; then
      warn "Active capsule '$(basename "$ACTIVE_CAPSULE")' status is still 'active'. Update status or handoff_notes before terminating."
    fi
  fi
fi

exit 0
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
  # Install full adapter for private repos — discover names from the private
  # manifest YAML, no private repo names hardcoded in this public script.
  if [[ -n "$PRIVM_DIR" && -d "$PRIVM_DIR/.git" ]]; then
    while IFS= read -r yaml_file; do
      while IFS=$'\t' read -r canonical_name _url; do
        [[ -z "$canonical_name" ]] && continue
        dir="$GITHUB_DIR/$canonical_name"
        [[ -d "$dir/.git" ]] || continue
        if [[ -f "$dir/.claude/hooks/pre_tool_use.sh" && "$FORCE_HOOKS" != true ]]; then
          echo "  ✓ $canonical_name (hooks already present)"
        else
          _install_full_adapter "$canonical_name"
        fi
      done < <(_extract_names_from_yaml "$yaml_file")
    done < <(find "$PRIVM_DIR/manifests" -name "*.yaml" 2>/dev/null | sort)
  fi
fi

# ── Hook health ───────────────────────────────────────────────────────────────
# Verify hooks are actually present + executable for every repo that should have
# them — both the ones installed above and the ones carrying committed hooks.
# This surfaces drift (a removed or non-executable hook) that the install step's
# "already present, skipping" path would otherwise hide. Warn-only; the smoke
# test below is the hard gate.
echo ""
echo "▶ Hook health"

_check_hook() {
  local name="$1"
  local dir="$GITHUB_DIR/$name"
  [[ -d "$dir/.git" ]] || return 0
  local hook="$dir/.claude/hooks/pre_tool_use.sh"
  if [[ -x "$hook" ]]; then
    printf "  ✓ %-20s hooks present\n" "$name"
  elif [[ -f "$hook" ]]; then
    printf "  ⚠ %-20s hook present but NOT executable\n" "$name"
  else
    printf "  ⚠ %-20s MISSING ContextGuard hook\n" "$name"
  fi
}

for repo in "${FULL_ADAPTER_REPOS[@]}" "${SHIM_REPOS[@]}" "${COMMITTED_HOOK_REPOS[@]}"; do
  _check_hook "$repo"
done

# ── Smoke test ────────────────────────────────────────────────────────────────
echo ""
echo "▶ Smoke test: cl session start"

declare -A EXPECTED_ANCHORS=(
  ["OperationsCenter"]="PlatformManifest"
  ["PlatformManifest"]="PlatformManifest"
)
# Add private repo smoke-test entries dynamically from the private manifest YAML.
if [[ -n "$PRIVM_DIR" && -d "$PRIVM_DIR/.git" ]]; then
  while IFS= read -r yaml_file; do
    while IFS=$'\t' read -r canonical_name _url; do
      [[ -z "$canonical_name" ]] && continue
      [[ -d "$GITHUB_DIR/$canonical_name/.git" ]] && EXPECTED_ANCHORS["$canonical_name"]="$(basename "$PRIVM_DIR")"
    done < <(_extract_names_from_yaml "$yaml_file")
  done < <(find "$PRIVM_DIR/manifests" -name "*.yaml" 2>/dev/null | sort)
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
