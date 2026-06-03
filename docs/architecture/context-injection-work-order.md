# Work Order — Context Injection & Tiered Memory

> **Tracks:** `docs/architecture/context-injection-spec.md` (the design).
> **Status:** Phase 0–2 (engine prototype, dark) **merged to `main`**; phases 3–5 gated.
> **Merged:** PR #39 (spec), #40 (spec §4 fix + wire draft), #41 (CI green). All on `main`.

This work order turns the spec into ordered, checkable work. The build is
deliberately **project-tier-only** and **gated after phase 2** — do not start the
cold/consolidation pipeline until warm injection has demonstrably helped.

## ▶ Resume here (operational status — read this first)

Everything below "Done" is **merged to `main`**; a fresh `git pull` on any machine
has it. The engine ships **dark** (`injection.enabled: false`), so live behaviour
is unchanged until someone deliberately wires + flips it.

**Verify you're in a good state (any machine):**
- `git -C PlatformManifest pull` → engine at `.context/.engine/route.py`, routes at
  `.context/routes.yaml`, leaf docs in `docs/inject/`.
- `.venv/bin/pytest tests/test_context_router.py -q` → 21 pass (or full suite 189).
- `grep -nA1 injection .context/config.yaml` → `enabled: false` (still dark).

**The next decision is yours, and it is a fork — do NOT skip to Phase 3:**
1. **Phase 2-wire** (the one risky step). Splice `docs/architecture/phase2-wire-draft.sh`
   into `.claude/hooks/pre_tool_use.sh` above the final `exit 0`, flip the flag,
   smoke-test in a throwaway session. Protocol already verified (below). Risk:
   a hook bug = "parole-officer" lockout, so test before trusting.
2. **Run the §7a gate.** Use warm injection live for a real window, then answer one
   question: *did it measurably cut convention violations / rework?*
   - **No →** STOP. Hot-trim + warm-injection may be the entire win at this scale;
     Phases 3–5 are cost you shouldn't pay.
   - **Yes →** build Phase 3–5 (cold store, hot-trim, campaign formalization,
     consolidation).

**Independent of the gate:** productionization (move the engine into ContextLifecycle)
and the doc-reconciliation track can happen any time. Platform/cross-repo tier and
the `~/.claude` merge stay deferred.

**Context that bit us last time (so you don't rediscover it):**
- An OperationsCenter "Operations Center Bot" auto-rebases/squash-force-pushes
  feature branches. Branch off `main`, push, and merge promptly — long-lived
  manual branches will collide with it.
- `main` is **unprotected** (no required checks), so red CI can merge. Check CI
  yourself before merging.
- CI installs `repograph` + `custodian` from public git; the audit needs the
  `REPOGRAPH_BOUNDARY_ARTIFACT_B64` repo secret (already set).

## Done in this PR (Phase 0–2 prototype, shipped DARK)

- [x] **Router engine** — `.context/.engine/route.py`: all-matches glob routing,
      injection budget + priority, `engine_compat` version-degradation, `## Inject`
      extraction. Pure stdlib + PyYAML; never raises to a hook caller.
- [x] **Routing table** — `.context/routes.yaml` (5 real PM domains).
- [x] **Warm leaf docs** — `docs/inject/{loader,projection,visibility,schemas,provisioning}.md`,
      each `## Inject` (auto-injected) + `## Reference` (pointer).
- [x] **Cold-store scaffold** — `.context/knowledge/` (empty until phase 3).
- [x] **Dark flag** — `config.yaml` `injection.enabled: false`; engine is not
      invoked from any hook, so live behaviour is unchanged.
- [x] **Tests** — `tests/test_context_router.py` (20 cases): globbing, all-matches,
      budget/priority, version degradation, `## Inject` extraction, e2e.

## Phase 2-wire — connect to the live hook (NOT in this PR; do next, carefully)

The single risky step: invoking the engine from `pre_tool_use.sh`. Deferred here
because a hook bug causes the "parole-officer" lockout, and it needs the exact
PreToolUse context-injection protocol verified first.

**Protocol verified** (Claude Code Hooks reference):

- [x] PreToolUse injects via stdout JSON, parsed **only on exit 0**:
      `{"hookSpecificOutput":{"hookEventName":"PreToolUse","additionalContext":"<str>"}}`.
      Omitting `permissionDecision` leaves the normal permission flow intact — we
      only add context. `exit 2` blocks (stdout ignored, stderr → model);
      injection must never reach it. `additionalContext` is capped at 10k chars.
- [x] **Spec §4 corrected:** PostToolUse **does** support `additionalContext`
      (the spec had claimed otherwise — now fixed). Does not change our choice —
      PreToolUse is still correct, since the point is to inject *before* the write.
- [x] **`jq` is not installed on the dev box.** The live hook already falls back
      to `python3`; the draft uses `python3` for both path-handling and JSON
      emission, so it is consistent and needs no `jq`.

**Draft, validated, parked:** `docs/architecture/phase2-wire-draft.sh` — the exact
block to splice in just above the final `exit 0`. End-to-end tested against the
real engine: absolute→repo-relative path strip, all-matches selection, valid
round-trippable JSON, empty-on-no-match. **Not yet in the live hook** (editing the
hook mid-session is the lockout risk itself).

- [ ] Splice the draft block into `pre_tool_use.sh` above the final `exit 0`.
- [ ] Smoke-test in a throwaway session (flag on) before trusting it.
- [ ] Keep `injection.enabled: false` until validated; flip per §7a.

## Gate (spec §7a) — evaluate before building the pipeline

- [ ] Run warm injection in the wild for a real window.
- [ ] Decide: did it demonstrably reduce convention violations / rework? If **no**,
      stop — hot-trim + warm-injection may be the whole win at this scale.

## Phase 3–5 (gated — only if the gate passes)

- [ ] **Cold store** — `.context/knowledge/` item format (§2.6), continuous
      capture + Stop-hook seal/forcing-function (§2.3), grep index, router
      cold-topic surfacing so cold isn't write-only.
- [ ] **Hot trim** — shrink `.console/.context` to the anchor (§5).
- [ ] **Campaign formalization** — `task.md` front-matter (`campaign_id`/`status`,
      §2.2b); automatic consolidation trigger (§2.3) — NOT a manual command alone.
- [ ] **Consolidation** — `cl consolidate`: distill cold→warm under the
      consequence-veto + usage-decay-with-pinning (§2.4); session-dir pruning.

## Productionization (separate, spec §1)

- [ ] Relocate the engine from `.context/.engine/` (prototype home) into the
      **ContextLifecycle** repo; install via `provision.sh` / `cl context init`.
      Keep `routes.yaml`, leaf docs, and cold store in-repo.

## Deferred (spec §7b / §0.1)

- [ ] **Platform/cross-repo tier** — publish-down; build-deferred until a
      cross-repo sync channel exists and repo count makes manual sharing painful.
- [ ] **`~/.claude` memory merge** — separate future sync task; untouched here.

## Doc-reconciliation track (spec §7c — independent)

- [ ] Reconcile `.console/backlog.md` against repo reality; refresh
      ProtocolWarden + protocolwarden.github.io doc surfaces.
