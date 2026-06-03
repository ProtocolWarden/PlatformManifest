# =============================================================================
# Phase 2-wire — DRAFT  (NOT yet spliced into .claude/hooks/pre_tool_use.sh)
# =============================================================================
# Tracks: docs/architecture/context-injection-spec.md §4, work-order "Phase 2-wire".
#
# What this is: the block to append to pre_tool_use.sh, just before the final
# `exit 0` (currently line 338). It emits warm leaf-doc conventions as
# PreToolUse `additionalContext` so Claude sees them BEFORE writing the file.
#
# Why it is parked in /docs and not in the live hook yet:
#   - The live hook governs this very session's tool calls; a syntax slip would
#     lock the operator out ("parole officer"). Splice only when ready to test.
#   - It stays INERT regardless: it reads `injection.enabled` from config.yaml,
#     which is `false`. Nothing injects until that flag is deliberately flipped.
#
# Verified protocol (Claude Code Hooks reference):
#   - PreToolUse injects via stdout JSON, ONLY parsed on exit 0:
#       {"hookSpecificOutput":{"hookEventName":"PreToolUse","additionalContext":"..."}}
#   - Omitting `permissionDecision` => normal permission flow proceeds; we ONLY
#     add context, we never auto-allow/deny.
#   - exit 2 => stdout ignored, stderr shown to model, tool BLOCKED. All the
#     enforcement above already uses this; injection must never reach it.
#   - additionalContext is capped at 10,000 chars (our budget keeps us far under).
#
# Safety contract for this block:
#   1. Runs only for Write|Edit.
#   2. Runs only AFTER every enforcement check above has passed.
#   3. Gated on injection.enabled (default false).
#   4. Wrapped so it can NEVER abort the hook or exit non-zero. A failure here
#      produces no output and falls through to `exit 0` — the tool proceeds.
# =============================================================================

# --- Warm context injection (Phase 2-wire) ---------------------------------
if [[ "$TOOL_NAME" == "Write" || "$TOOL_NAME" == "Edit" ]]; then
  # Dark flag — inert until explicitly enabled in .context/config.yaml.
  INJECT_ENABLED=false
  if [[ -f "${CONFIG_FILE}" ]] && command -v python3 &>/dev/null; then
    INJECT_ENABLED=$(python3 -c "
try:
    import yaml
    with open('${CONFIG_FILE}') as f:
        c = yaml.safe_load(f) or {}
    print(str(c.get('injection', {}).get('enabled', False)).lower())
except Exception:
    print('false')
" 2>/dev/null || echo "false")
  fi

  if [[ "$INJECT_ENABLED" == "true" ]]; then
    # Entire emission isolated: any failure is swallowed, never blocks the call.
    {
      ENGINE="${REPO_ROOT}/.context/.engine/route.py"
      # TARGET_PATH was resolved by the pre_write check above. routes.yaml uses
      # repo-relative globs, so strip the anchor prefix if the path is absolute.
      REL_PATH="${TARGET_PATH#${REPO_ROOT}/}"
      if [[ -n "$REL_PATH" && -f "$ENGINE" ]]; then
        CTX="$(python3 "$ENGINE" --target "$REL_PATH" --root "$REPO_ROOT" 2>/dev/null || true)"
        if [[ -n "$CTX" ]]; then
          # Emit additionalContext on exit 0. python3 json.dumps does the
          # escaping (python3 is already required above for YAML parsing).
          CTX="$CTX" python3 -c "
import json, os
ctx = os.environ.get('CTX', '')
print(json.dumps({
    'hookSpecificOutput': {
        'hookEventName': 'PreToolUse',
        'additionalContext': ctx,
    }
}))
" 2>/dev/null || true
        fi
      fi
    } || true
  fi
fi

# exit 0   <-- this block goes immediately ABOVE the existing final `exit 0`
