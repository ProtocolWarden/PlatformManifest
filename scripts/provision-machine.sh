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
  fi
  # Always (re)install editable so dependency changes from a git pull are
  # picked up on re-provision. pip is a near-no-op when nothing changed.
  "$venv/bin/pip" install --quiet --upgrade pip
  "$venv/bin/pip" install --quiet -e "$dir"
  echo "  ✓ $name venv ready"
}

_ensure_venv "$CL_DIR" "ContextLifecycle"
_ensure_venv "$RG_DIR" "RepoGraph"

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
FULL_ADAPTER_REPOS=("PlatformManifest")

# Repos that need the 9-LINE EXECUTOR SHIM (delegates enforcement to CL).
# TeamExecutor + CritiqueExecutor already carry committed hooks in-repo.
SHIM_REPOS=("DAGExecutor")

# Repos whose ContextGuard hooks are committed in-repo (not installed here).
# Listed so the hook-health check below can verify they're actually present —
# catches drift if a committed hook is removed or broken. (OperatorConsole is
# the launcher TUI and intentionally carries no hooks.)
COMMITTED_HOOK_REPOS=("OperationsCenter" "TeamExecutor" "CritiqueExecutor")

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
  # Install full adapter for private repos — discover names from PrivateManifest YAML,
  # no private repo names hardcoded in this public script.
  PRIVM_DIR="$GITHUB_DIR/PrivateManifest"
  if [[ -d "$PRIVM_DIR/.git" ]]; then
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
# Add private repo smoke-test entries dynamically from PrivateManifest YAML.
PRIVM_DIR="$GITHUB_DIR/PrivateManifest"
if [[ -d "$PRIVM_DIR/.git" ]]; then
  while IFS= read -r yaml_file; do
    while IFS=$'\t' read -r canonical_name _url; do
      [[ -z "$canonical_name" ]] && continue
      [[ -d "$GITHUB_DIR/$canonical_name/.git" ]] && EXPECTED_ANCHORS["$canonical_name"]="PrivateManifest"
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
