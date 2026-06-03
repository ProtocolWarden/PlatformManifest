# Work Order — Context Injection & Tiered Memory

> **Tracks:** `docs/architecture/context-injection-spec.md` (the design).
> **Status:** Phase 0–2 (engine prototype, dark) **merged to `main`**; Phase 2-wire
> **spliced + smoke-tested** on `feat/phase2-wire-context-injection` (still dark); phases 3–5 gated.
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
- `.venv/bin/pytest tests/test_context_router.py -q` → 36 pass (or full suite 204).
- `grep -nA1 injection .context/config.yaml` → `enabled: false` (still dark).

**Phase 2-wire is DONE** (branch `feat/phase2-wire-context-injection`): the draft
is spliced into `.claude/hooks/pre_tool_use.sh`, `bash -n`-validated before the
live swap, and smoke-tested through the real hook with the flag toggled on/off.
It is **still dark** (`injection.enabled: false`) — wiring ≠ activation.

**The next decision is yours, and it is a fork — do NOT skip to Phase 3:**
1. **Flip the flag** (`injection.enabled: true`) and run with warm injection live.
   The hook is already wired and inert-safe; this is the activation step. Risk is
   now low (a hook bug would have surfaced in the smoke test) — but watch the
   first live session.
2. **Run the §7a gate.** Use warm injection live for a real window, then answer one
   question: *did it measurably cut convention violations / rework?*
   - **No →** STOP. Hot-trim + warm-injection may be the entire win at this scale;
     Phases 3–5 are cost you shouldn't pay.
   - **Yes →** build Phase 3–5 (cold store, hot-trim, campaign formalization,
     consolidation).

**Status (2026-06-03):** Phases 2-wire, 3, 5 merged to `main` (PR #42); warm
injection LIVE. Both live-hook drafts **SPLICED** (PR #43): phase3-capture in
`stop.sh`, phase5-trigger in `pre_tool_use.sh` (flag-gated, warn/dry-run, never
block). **Productionized into ContextLifecycle** (CL PR #12): engine is now a CL
package + `cl context init`; this repo's `.context/.engine/` tracks it.
**Remaining:** Phase 4 hot-trim (OperatorConsole compiler — cross-repo) and
doc-reconciliation (§7c). Platform/cross-repo tier + `~/.claude` merge stay deferred.

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
- [x] **Tests** — `tests/test_context_router.py` (36 cases): globbing, all-matches,
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

- [x] Splice the draft block into `pre_tool_use.sh` above the final `exit 0`.
      Done on branch `feat/phase2-wire-context-injection` — block lands between
      `# All checks passed` and the final `exit 0` (hook 338 → 381 lines).
      Validated via `bash -n` in a temp copy *before* the live swap (the hook
      governs the operator's own session, so a syntax slip = lockout).
- [x] Smoke-test (flag on) before trusting it. Exercised the **live hook file**
      as a subprocess (flag flipped on+restored atomically, session never hot):
      Write→`loader.py` emits valid PreToolUse `additionalContext` JSON (944
      chars, exit 0); Write→`README.md` (no route) emits nothing, exit 0;
      flag-off → fully inert. Router unit tests 36/36.
- [ ] Keep `injection.enabled: false` until validated; flip per §7a. **Still
      dark** — the flip is the gate decision, deliberately not done here.

## Gate (spec §7a) — JUDGED PASS 2026-06-03 (operator-delegated)

- [x] Activated: `injection.enabled: true` (config.yaml), engine hardened (11
      defects fixed, 36 router tests green), hook block can never block a call.
- [x] **Verdict: PASS — proceed to Phases 3–5, built incrementally.** Basis:
      injection fires correctly (PreToolUse, all-matches, budget-bounded) and the
      routed payloads are substantive prevention-oriented conventions (fail-closed
      visibility, redaction-first, idempotency, hook exit-code contract), at near-
      zero cost on no-match. **Caveat:** §7a's literal "demonstrably reduced
      rework over a real window" is a multi-session empirical measurement not
      certifiable in one session; this is a reasoned forward judgment under the
      operator's explicit direction to build the full spec. Re-evaluate against
      real usage as it accumulates; flip the flag back if it proves noisy.

## Phase 3–5 (gated — only if the gate passes)

- [x] **Cold store** — DONE (branch `feat/phase2-wire-context-injection`).
      `.context/.engine/cold.py`: §2.6 parse/validate/write (fail-soft, never
      raises), a load-index pass (the grep index = on-disk frontmatter) and a
      one-line surfacing pass (`topic — path — finding`, capped). Router
      integration in `route.py` (cold-surfacing + cap-loading helpers,
      COLD_SURFACE_CAP=5): the same build pass appends "Related cold topics
      (pull on demand):",
      additive (surfaces even with no warm route), bounded, double-wrapped to
      never raise — verified under adversarial malformed cold items (exit 0, no
      traceback). 2 fixture items + `tests/test_cold_store.py` (30 tests green).
      Stop-hook capture forcing-function **SPLICED LIVE** into
      `.claude/hooks/stop.sh` (2026-06-03) — `bash -n`-validated before swap;
      smoke-tested (fires when an active capsule has `changed_files` but no
      `findings`; silent when findings present / "no durable findings" recorded /
      flag off / no edits). Warn-only, never blocks. Draft retained at
      `docs/architecture/phase3-capture-draft.sh`. Built via workflow (failed on a
      post-impl schema hiccup; salvaged + proven by hand).
- [ ] **Hot trim** — shrink `.console/.context` to the anchor (§5). **NOT
      prototyped here** — the compiled blob (currently ~139 KB) is produced by
      **OperatorConsole's** compiler, not this repo, and the live OC loop reads
      it. Needs a cross-repo change in OperatorConsole + a defined anchor; queued
      for a deliberate manual pass, not an autonomous workflow.
- [x] **Campaign formalization (§2.2b)** — DONE (prototype). `.console/task.md`
      carries additive `campaign_id`/`status` front-matter; `.context/.engine/campaign.py`
      `parse_task()` reads it (front-matter-less fallback intact). The boundary is
      the campaign_id change. The **automatic trigger (§2.3)** is **SPLICED LIVE**
      into `.claude/hooks/pre_tool_use.sh` (2026-06-03), once-per-boundary via a
      cheap `task.md`-mtime throttle (no SessionStart hook needed). Diverged from
      the parked draft: (1) registers `campaign.py` in `sys.modules` before
      `exec_module` — `@dataclass` needs it (Py 3.14); (2) mtime throttle keyed on
      `SESSION_MARKER` instead of a nonexistent `SESSION_DIR`; (3) emits the
      WHOLE-REPO dry-run plan (scoping `--campaign` to the new id gave "nothing to
      do"). `bash -n`-validated; smoke-tested (silent first-sight/unchanged/flag-off;
      fires on campaign_id change + status→done). Dry-run only — never `--apply`,
      never blocks. Draft retained at `docs/architecture/phase5-trigger-draft.sh`.
- [x] **Consolidation (§2.4)** — DONE (prototype, `cl consolidate` logic).
      `.context/.engine/{consolidate,distill,prune}.py`: consequence-veto (real
      `acted_on_commit` sha + `tests_green`, never confidence/citations),
      usage-decay reading `last_injected` with **pinned items decay-exempt**,
      cold→warm distill (materializes a leaf doc + routes entry, flips tier),
      session-dir pruning. **DRY-RUN by default** — verified zero mutation on the
      real repo by before/after checksum; `--apply` to execute. 38 tests on temp
      fixtures. Productionizing as the real `cl consolidate` CLI belongs to the
      ContextLifecycle move below.

## Productionization (separate, spec §1)

- [x] **DONE** (ContextLifecycle PR #12, 2026-06-03). The engine now lives in CL
      at `src/context_lifecycle/context_engine/` (the canonical source); `cl context
      init` idempotently scaffolds it into a repo's `.context/.engine/` plus
      `routes.yaml` / `docs/inject/` / `.context/knowledge/` (engine refreshed each
      run, authored state never clobbered). The three hook blocks were ported into
      CL's canonical `adapters/claude/hooks/`, so `install.sh` propagates them to
      every repo. Scaffold-into-repo model (hooks call the local file — no import
      path needed at hook time). This repo's `.context/.engine/` is byte-identical
      to CL's package and now tracks it (re-sync with `cl context init`). Engine
      tests moved to CL (227 green); the 6 engine modules are marked vendored in
      CL's custodian config. (Also greened CL's CI, red since 5/30.)

## Deferred (spec §7b / §0.1)

- [ ] **Platform/cross-repo tier** — publish-down; build-deferred until a
      cross-repo sync channel exists and repo count makes manual sharing painful.
- [ ] **`~/.claude` memory merge** — separate future sync task; untouched here.

## Doc-reconciliation track (spec §7c — independent)

- [ ] Reconcile `.console/backlog.md` against repo reality; refresh
      ProtocolWarden + protocolwarden.github.io doc surfaces.
