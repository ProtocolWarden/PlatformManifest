# =============================================================================
# Phase 5-trigger — SPLICED 2026-06-03 into .claude/hooks/pre_tool_use.sh (with
# changes — see the work-order: sys.modules registration, SESSION_MARKER mtime
# throttle, whole-repo dry-run). This file is the retained design-of-record.
# =============================================================================
# Tracks: docs/architecture/context-injection-spec.md §2.2, §2.3, §2.4, §5.
# Sibling of phase2-wire-draft.sh and phase3-capture-draft.sh.
#
# What this is: the AUTOMATIC consolidation trigger (§2.3). It fires the
# campaign-close distill/prune pass when a campaign boundary changes. The pass
# itself is .context/.engine/consolidate.py — which is DRY-RUN BY DEFAULT and
# only mutates with --apply.
#
# Where it would splice: a SessionStart hook (or the top of pre_tool_use.sh,
# once per session via the SESSION_MARKER), immediately AFTER the existing
# enforcement checks and BEFORE the final `exit 0`. It is the §2.3 boundary
# detector: it asks campaign.boundary_changed() whether .console/task.md's
# campaign_id/status (or, for the still-freeform file, the Objective text)
# changed vs the last-seen state recorded under the session marker.
#
# Why it is parked in /docs and not in a live hook yet:
#   - The live hooks govern this very session; a syntax slip risks operator
#     lockout. Splice only when ready to test — manually, like Phase 2 / 3.
#   - It stays INERT regardless: gated on injection.enabled (currently the only
#     flag this feature is gated on).
#   - CRITICAL: even when spliced, it must run consolidate.py WITHOUT --apply
#     (dry-run) until an operator has reviewed a few plans. The default is the
#     safe one; --apply is a deliberate, separate step.
#
# Safety contract for this block:
#   1. Gated on injection.enabled (default false) — inert until flipped.
#   2. Fires AT MOST once per boundary change (records last-seen campaign_id /
#      Objective hash under the session marker; no re-fire until it changes).
#   3. Runs consolidate.py in DRY-RUN by default — emits the plan to stderr as a
#      warn, never mutates, never blocks.
#   4. Wrapped in `{ ... } || true` so ANY failure falls through to exit 0. The
#      engine itself never raises (spec §1); this is belt-and-suspenders.
#
# PREREQUISITE (documented, not created here): .console/task.md carries the
# §2.2b front-matter (campaign_id/status/started) — already added as an additive
# template block. boundary_changed() also tolerates the front-matter-less file
# via the Objective-hash fallback.
# =============================================================================

# --- Campaign-close consolidation trigger (Phase 5) ------------------------
# if [[ "$INJECT_ENABLED" == "true" ]]; then
#   {
#     ENGINE="${REPO_ROOT}/.context/.engine/consolidate.py"
#     CAMP="${REPO_ROOT}/.context/.engine/campaign.py"
#     TASK="${REPO_ROOT}/.console/task.md"
#     # Last-seen boundary state recorded under the session marker dir so the
#     # trigger fires at most once per boundary change.
#     SEEN_FILE="${SESSION_DIR}/.last-seen-campaign"
#     LAST_SEEN_ID=""
#     LAST_SEEN_HASH=""
#     if [[ -f "$SEEN_FILE" ]]; then
#       LAST_SEEN_ID="$(sed -n '1p' "$SEEN_FILE" 2>/dev/null || true)"
#       LAST_SEEN_HASH="$(sed -n '2p' "$SEEN_FILE" 2>/dev/null || true)"
#     fi
#
#     CHANGED=$(python3 -c "
# import sys, importlib.util
# spec = importlib.util.spec_from_file_location('cl_campaign', '${CAMP}')
# m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
# from pathlib import Path
# changed = m.boundary_changed(Path('${TASK}'),
#                              '${LAST_SEEN_ID}' or None,
#                              '${LAST_SEEN_HASH}' or None)
# camp = m.parse_task(Path('${TASK}'))
# cid = (camp.campaign_id if camp else '') or ''
# h = m.objective_hash(camp.objective) if camp else ''
# print(('true' if changed else 'false') + '\t' + cid + '\t' + h)
# " 2>/dev/null || printf 'false\t\t')
#
#     FIRE="$(printf '%s' "$CHANGED" | cut -f1)"
#     NEW_ID="$(printf '%s' "$CHANGED" | cut -f2)"
#     NEW_HASH="$(printf '%s' "$CHANGED" | cut -f3)"
#
#     if [[ "$FIRE" == "true" ]]; then
#       # DRY-RUN by default: emit the plan as a warn, mutate nothing.
#       PLAN="$(python3 "$ENGINE" --root "$REPO_ROOT" ${NEW_ID:+--campaign "$NEW_ID"} 2>/dev/null || true)"
#       if [[ -n "$PLAN" ]]; then
#         echo "ContextGuard: campaign boundary changed — consolidation plan (dry-run):" >&2
#         printf '%s\n' "$PLAN" >&2
#         echo "  Review, then run: python3 ${ENGINE} --root ${REPO_ROOT} --apply" >&2
#       fi
#       # Record the new last-seen state so we don't re-fire until it changes.
#       printf '%s\n%s\n' "$NEW_ID" "$NEW_HASH" > "$SEEN_FILE" 2>/dev/null || true
#     fi
#   } || true
# fi

# exit 0   <-- this block goes immediately ABOVE the existing final `exit 0`
