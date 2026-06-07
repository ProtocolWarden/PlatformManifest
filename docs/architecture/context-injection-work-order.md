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
Doc-reconciliation (§7c) **done** (ProtocolWarden PR #4, github.io PR #8 —
SyncMechanism catalog entry + ContextLifecycle tiered-memory docs).
**Phase 4 hot-trim DONE** (OperatorConsole PR #62, 2026-06-03) — compile-time
trim of the log + historical backlog sections in `bootstrap.py`; non-destructive
(source `.console/*.md` untouched), tunable via `CONSOLE_LOG_RECENT_ENTRIES`,
applies fleet-wide on each repo's next console launch. Public Hot-tier docs added
(github.io contextlifecycle.md). **§7a re-evaluated 2026-06-04: KEEP** — see the
re-evaluation subsection under the Gate; warm injection confirmed live-useful
(direct hit on PR #53's provision-script edits), limiter is route coverage. **Remaining (separate concern):** active-backlog
*content* reconciliation — stale `In Progress` items the compiler can't judge;
OperationsCenter's `.console/` is live-loop-owned, so it needs a loop-paused
window or operator input. Platform/cross-repo tier + `~/.claude` merge stay
deferred (spec §7b/§0.1).

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
- [x] Keep `injection.enabled: false` until validated; flip per §7a. Flipped
      with the gate decision below (2026-06-03); live since.

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

### §7a re-evaluation — 2026-06-04 (empirical, post-live-window)

- [x] **Verdict: KEEP — warm injection re-affirmed.** Evidence from the live
      window (2026-06-03 → 06-04):
      - **Engine healthy:** live run against `scripts/provision-machine.sh`
        emits the correct provisioning conventions, exit 0; router behavior
        unchanged.
      - **One routed-path edit occurred** (PR #53, `scripts/provision*.sh` in
        the private-manifest role generalization). The hook injected the
        provisioning leaf doc pre-edit and the resulting discovery-function
        work conformed to every injected convention (idempotent re-run safety,
        bootstrap-safe no-hard-fail, exit-code contract). Direct positive hit.
      - **Zero noise:** no false injections, silence on no-match, no observed
        cost. No reason to flip the flag back.
      - **Limiter is route COVERAGE, not correctness:** the week's heaviest
        convention-rework (canonical B64 audit-workflow pattern, venv-guard
        CI mismatch — re-derived repeatedly across the fleet-green batch)
        happened in `.github/workflows/**` and `.custodian/*.yaml`, which no
        route matched. **DONE (same day):** `docs/inject/ci-conventions.md`
        added and routed on both globs (B64 step, hooksPath, venv-guard,
        fleet-coupled custodian@main, semantic workflow naming,
        plugin_audit_keys, no-baked-paths/fail-closed, K2/DC7 exclusions).

### Targeted second-consumer rollout — 2026-06-04

- [x] **Custodian** (Custodian #34): second consumer of the CL engine.
      `cl context init` scaffold + a SLIM injection-only PreToolUse hook (no
      ContextGuard — never blocks, always exit 0; Custodian sessions were
      previously hook-free, so the full guard stack would have been scope
      creep). Routes: the same two CI globs → a copy of `ci-conventions.md`
      (THIS repo's copy is canonical — noted in the doc). `.gitignore`
      narrowed so `.claude/` ships. Verified: match/no-match/flag-off, audit
      clean with artifact + B2 fail-closed without.
- [x] **OperationsCenter: SKIPPED — operator decision 2026-06-04.** OC's
      `.context/` was deliberately removed (cognition is hosted by the
      anchoring manifest; OC's hook resolves REPO_ROOT from `CL_ANCHOR`, and
      OC run capsules live in the anchor's `.context/sessions/`). Repo-local
      warm injection therefore conflicts with a recorded decision, and
      anchor-resolved routing can't match OC-checkout paths — OC is exactly
      the cross-repo-tier case §7b defers. Revisit only when/if that tier is
      built. A scaffold mistakenly created during the attempt was fully
      reverted (OC tree clean).
      - **Phase 3 capture: 0 cold-store entries captured** since activation —
        `.context/knowledge/` unchanged since PR #42. The capsules the stop-hook
        nudge scans are machine-generated lease/run records, not authored
        session capsules; the stderr nudge has produced no behavior change.
        Warn-only, so cost ≈ 0; leave as-is, but don't count it as working.
        **→ CLOSED AS SUPERSEDED, operator decision 2026-06-05 (see below).**
      - **Phase 5 trigger: provably runs** (campaign-boundary markers present
        for 3 sessions), dry-run only, harmless.

### Phase-3 capture closure — 2026-06-05 (operator decision: superseded)

The cold-store **capture path** (stop-hook nudge → authored capsule findings →
`.context/knowledge/`) is CLOSED AS SUPERSEDED, not fixed. While it sat inert
(0 entries), the job it was designed for got done — repeatedly, at fleet scale —
through a surface that won on merit:

    session → `.console/log.md`   (capture: tracked, synced, R1-gated)
            → `cl reconcile` worksheet/prune   (consolidate: doc-gap gated)
            → repo docs + `docs/inject/` leaf docs   (warm tier)

Evidence: the ci-conventions leaf doc was distilled from `.console` history
(phase-5 consolidation in everything but name); the fleet-wide reconciliation
arc (22/22 repos) is a scheduled, enforced distillation pipeline over the same
surface; R1 *forces* the capture→consolidate cycle by capping log size. Fixing
the nudge would mean maintaining a second capture surface — unsynced,
unreconciled, ungated — for the same class of insight.

What changed: the inert nudge block in `.claude/hooks/stop.sh` is retired
(replaced by a pointer comment). The cold store (`.context/knowledge/`) and its
router surfacing remain LIVE as a **manual-only** surface — seal an entry by
hand when a micro-insight has no natural `.console`/doc home. Phase-5
consolidation stays dry-run over it, unchanged. Reopen only if manual sealing
reveals real demand for automated capture.

## Phase 3–5 (gated — only if the gate passes)

> **STATUS NOTE — consolidation middle DORMANT (2026-06-06, completeness
> audit).** Everything below is built, tested, and wired — and the
> cold→consolidate→promote→decay chain has **never fired for real**, because
> two operational preconditions have never been met: (1) no campaign has ever
> been minted (`task.md` front-matter is still the template, so
> `boundary_changed()` never returns True); (2) nothing writes consequence
> fields (`acted_on_commit`/`tests_green`) onto cold items, so even a fired
> trigger would promote nothing. This is an accepted operational state, not a
> bug: manual cold-store curation + warm injection are the live path (same
> logic as the phase-3 closure — the surface that wins on merit). The chain
> activates with no code changes when (a) campaign ids are minted in `task.md`
> at objective boundaries AND (b) a consequence writer exists (e.g. a future
> `cl seal`). Do not "fix" the dormancy unprompted; revisit only if manual
> curation becomes toil.

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
- [x] **Hot trim** — shrink `.console/.context` to the anchor (§5). **DONE**
      (OperatorConsole PR #62, 2026-06-03). Implemented in OperatorConsole's
      compiler (`bootstrap.py`), not this repo, since that's what produces the
      blob the live loop reads. `_trim_log()` keeps the preamble + most-recent N
      log entries (newest-last) + a pointer note; `_trim_backlog()` drops sections
      whose heading matches historical/completed patterns (Done / Recently
      Completed / Previously In Progress / Cycle … updates / Archived), keeping
      active (In Progress / Up Next / unrecognized) sections. Non-destructive
      (source `.console/*.md` untouched), tunable via `CONSOLE_LOG_RECENT_ENTRIES`
      (default 5; 0 disables), applies fleet-wide on each repo's next console
      launch. 8 tests (`tests/test_bootstrap_trim.py`). Measured: PM 2142→138,
      OperationsCenter ~3300→686, others ≤234. **Note:** the trim drops *historical*
      backlog automatically, but reconciling stale *active* (`In Progress`) items
      is a content judgment the compiler can't make — tracked separately above.
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
- [ ] **Warn-only violation logger (spec §4)** — deferred out of v1
      (2026-06-06; spec §4 status note). Was claimed "ships in v1" but never
      built; `stopped_logged_violation()` returns `False` until it exists.
      Build trigger: a real recurring violation worth seeding a rule from.

## Doc-reconciliation track (spec §7c — independent)

- [x] **DONE 2026-06-03** (ProtocolWarden PR #4, protocolwarden.github.io PR #8).
      Ground-truthed against the manifest's 19 public repos: `.console/backlog.md`
      is the unpopulated template (nothing to reconcile / no durable knowledge to
      migrate). Refreshed the external doc surface for the two concrete gaps:
      (1) **SyncMechanism** (public, `fleet_sync_mechanism`) was missing — added a
      repo page + nav + catalog tables (github.io) and the profile README catalog
      + diagram (ProtocolWarden); (2) **ContextLifecycle's** now-shipped
      context-injection / tiered-memory capability was undocumented — added a
      section + refreshed catalog lines. Boundary-checked against the manifest:
      repos absent from the public manifest correctly stay out of the public
      catalog (no private names introduced). A deeper page-by-page audit of the
      ~90-doc site beyond these verified gaps is left as future doc work, not
      part of this track's actionable scope.
