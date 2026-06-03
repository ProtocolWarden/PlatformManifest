# =============================================================================
# Phase 3-capture — DRAFT  (NOT yet spliced into .claude/hooks/stop.sh)
# =============================================================================
# Tracks: docs/architecture/context-injection-spec.md §2.3 (capture forcing
# function), §2.2 (continuous capture intake). Sibling of phase2-wire-draft.sh.
#
# What this is: the block to append to stop.sh, immediately ABOVE the existing
# final `exit 0` (currently the last line, line 124, after the checkpoint-warn
# and capsule-status-warn checks). It is the §2.3 "capture forcing function":
# on Stop, if the session made edits but the active capsule recorded no durable
# findings, it prompts (warn-only, never blocks) for a one-line capture.
#
# Why it is parked in /docs and not in the live hook yet:
#   - The live Stop hook governs this very session's termination; a syntax slip
#     risks operator lockout. Splice only when ready to test — manually, the
#     same caution Phase 2-wire used.
#   - It stays INERT regardless: it reads `injection.enabled` from config.yaml
#     (currently the only flag this whole feature is gated on). Until that flag
#     is honoured here, nothing prompts.
#
# Verified protocol (Claude Code Hooks reference):
#   - Stop hooks surface stderr to the operator but cannot hard-block session
#     end in all cases; the prompt is a WARN, the choice is explicit and
#     non-blocking. Match the surrounding `warn` / `echo ... >&2` style already
#     in stop.sh (checkpoint-warn, capsule-status-warn).
#   - exit 0 always: the block must fall through to the existing final exit 0.
#
# Safety contract for this block:
#   1. Gated on injection.enabled (default false) — inert until flipped, exactly
#      like Phase 2.
#   2. Reuses variables stop.sh already computes: REPO_ROOT, CONFIG_FILE,
#      SESSION_MARKER, CAPSULE_DIR / ACTIVE_CAPSULE. No new git dependency, no
#      Path.stat patching (version-insensitive: dev 3.14 / CI 3.11).
#   3. Wrapped in `{ ... } || true` so ANY failure falls through to exit 0. The
#      hook never blocks (spec §1).
#
# PREREQUISITE (documented, not created here): the capsule template/schema must
# gain a `findings:` list field (the continuous-capture intake of §2.2/§2.3).
# Until it exists, an absent field is treated as "no findings" and the prompt
# may fire on every edited session. The draft ships PARKED/inert so this is low
# risk; add `findings: []` to the capsule template before splicing.
#
# SEAL RELATIONSHIP (documented, not inlined here): this prompt is the forcing
# FUNCTION. The actual seal — capsule `findings:` entries -> a §2.6 cold item at
# .context/knowledge/<slug>.md — is performed by `cl seal`, which calls
# .context/.engine/cold.py:write_item(). That seal logic lives in the engine and
# is exercised by tests NOW (tests/test_cold_store.py); wiring `cl seal` into the
# live Stop hook is the manual, post-validation step the operator performs later,
# the same caution as Phase 2. This block only PROMPTS; it does not seal.
# =============================================================================

# --- Capture forcing function (Phase 3-capture) ----------------------------
{
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
    # 1) Detect "session made edits" and "capsule has no findings" from the
    #    ACTIVE capsule. Preferred over a git/find-newer scan: it reads capsule
    #    fields stop.sh already locates (CAPSULE_DIR / ACTIVE_CAPSULE), keeping
    #    this version-insensitive (no git state, no Path.stat patching).
    #
    #    Alternative considered (documented, NOT used): a filesystem proxy
    #      find "$REPO_ROOT/src" "$REPO_ROOT/docs" -type f -newer "$SESSION_MARKER"
    #    detects edits without the capsule, but depends on which dirs are bounded
    #    and double-counts tool-driven writes. The capsule field read is the
    #    intended intake of §2.2 and is preferred.
    #
    #    Capsule fields:
    #      changed_files: [...]   # edits this session made (intake of §2.2)
    #      findings: [...]        # NEW field (see PREREQUISITE above)
    CAPSULE_DIR="${REPO_ROOT}/${CAPSULE_PATH}"
    if [[ -d "$CAPSULE_DIR" ]] && command -v python3 &>/dev/null; then
      ACTIVE_CAPSULE=$(find "$CAPSULE_DIR" -name "*.yaml" -not -name ".gitkeep" | head -1)
      if [[ -n "$ACTIVE_CAPSULE" ]]; then
        NEEDS_CAPTURE=$(python3 -c "
try:
    import yaml
    with open('${ACTIVE_CAPSULE}') as f:
        d = yaml.safe_load(f) or {}
    edited = bool(d.get('changed_files') or [])
    findings = d.get('findings') or []
    # 'no durable findings' recorded explicitly counts as satisfied.
    explicit_none = any(
        isinstance(x, str) and 'no durable findings' in x.lower()
        for x in (findings if isinstance(findings, list) else [])
    )
    print('true' if (edited and not findings and not explicit_none) else 'false')
except Exception:
    print('false')
" 2>/dev/null || echo "false")

        if [[ "$NEEDS_CAPTURE" == "true" ]]; then
          # 2) Soft prompt (spec §9 "leaning soft"): warn-only, never blocks.
          echo "ContextGuard: this session edited files but recorded no durable findings." >&2
          echo "  Add a one-line finding to the active capsule (findings:) or record" >&2
          echo "  \"no durable findings\" explicitly. See docs/architecture/context-injection-spec.md §2.3." >&2
        fi
      fi
    fi
  fi
} || true

# exit 0   <-- this block goes immediately ABOVE the existing final `exit 0`
