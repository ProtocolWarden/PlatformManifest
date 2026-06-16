# Capability Plane — Completion Spec (Phases 1–6)

_Status: Phase 1 SHIPPED (OperatorConsole Fleet-Capabilities consumer). The 3
open decisions are RESOLVED via adversarial analysis (see "Resolved decisions"
below) — net: build one CAP1 gate, then populate; CAP2 and CAP3 deferred behind
explicit triggers. Phases 4–6 documented and gated._

This spec completes the capability registry beyond v1 (schema + 3 seeds + CAP1).
It was authored directly (not via the OperationsCenter spec-author/campaign
channel) and **hardened against an adversarial review** that verified every
technical claim against code; the findings below are baked in, not aspirational.

## Principle (load-bearing — do not drift)
A **fleet-legibility / cognition** layer, NOT a runtime. *"The runtime already
exists; make it legible."* No harness-runtime repo; no per-behavior SKILL.md.
Capabilities are a **read-model loaded into context**. `routing.preferred_lane`
is **descriptive only** until Phase 4 (gated). Layer contract is unchanged:
RepoGraph = language (import-free of the fleet; `invocation.ref` opaque),
PlatformManifest = instances + read query, Custodian = reality check,
OperatorConsole / OperationsCenter = consumers.

## Invariants carried from v1 (already enforced at RepoGraph load)
1. **Exactly one `owns` edge per capability** — enforced in `validation.py`
   (`owns_count != 1` raises at registry build). A violating registry cannot load.
2. **`invocation.ref` resolves in the owning repo** — Custodian **CAP1**, live.
3. **Repo-targeting edges resolve** — `owns/targets/executes/requires/validates`
   targets must be known repo_ids; enforced at compile (`known_repo_ids`). A
   dangling `requires`/`validated_by` repo fails the build, before any detector.

## Cross-cutting reality the adversarial review surfaced (READ THIS FIRST)
- **CAP detectors that need the cross-repo registry are structurally inert in
  single-repo CI.** CI runners check out one repo; CAP1 finds the registry only
  via a sibling `../PlatformManifest`, which is absent in CI → it returns 0. CAP1
  (and any registry-dependent CAP detector) does real work **only locally /
  pre-push** where the workspace siblings exist. Therefore any promise of the
  form "each ref passes CAP1 before merge" has **no CI enforcement venue** today.
  Phase 2 must define that venue explicitly (options: a local multi-repo
  pre-merge sweep with all siblings; an OperationsCenter dispatch job that checks
  out every owning repo; a CI job that checks out siblings). Until chosen,
  population correctness rests on local pre-push discipline — state that, don't
  imply CI gates it.
- **Doctor does not validate `audit.capabilities.*` sub-keys.** `_KNOWN_AUDIT_KEYS`
  whitelists only the top-level `capabilities` key; sub-flags nest under it and
  are **not** typo-guarded. A misspelled `coverage_enforce` is silently ignored
  (fails open). New sub-flags need NO `_KNOWN_AUDIT_KEYS` change — but a typo
  guard for known sub-keys is a real, missing safety the spec should add.
- **Dormancy = in-detector early-return on a falsy flag**, not a doctor key.
  `build_capability_detectors()` is unconditionally run; each detector must
  `return count=0` when its enable-flag is unset (CAP1's pattern). This is
  necessary because fleet CI installs `custodian@main`.

---

## Phase 1 — Session-start legibility (SHIPPED)
**Consumer:** OperatorConsole's `build_resume_prompt` (the context-bootstrap
consumer) appends a **Fleet Capabilities** section (grouped by owner; name ·
target_scope · risk · lane) to the compiled `.console/.context`.
**Read-path:** reads PlatformManifest `capabilities.yaml` **directly via PyYAML**
— no `platform_manifest`/`repograph` import, no RepoGraph graph-compile. The flat
authoring YAML already carries `owner_repo_id`/`target_scope`/`risk`/`routing`.
(The obvious `load_default_capabilities()` path was rejected: it triggers a full
RepoGraph compile and a sibling-checkout import that OperatorConsole — not a pip
package — cannot satisfy.) Located in-repo when anchored at PlatformManifest,
else a sibling checkout. **Fail-soft** (missing/malformed → section omitted,
never blocks compilation). Private capabilities (`visibility != public`) never
surfaced. **Known limitation:** whether the launch path auto-regenerates
`.console/.context` (vs. an operator-invoked console resume/bootstrap command) is
a pre-existing question that affects all sections, not just this one.

## Phase 2 — Population to fleet coverage + anti-omission detector
**Goal:** the registry reflects the actual **public** fleet, and stays complete.
- Author every real public capability into `capabilities.yaml`. NO private-repo
  capabilities (Phase 5). Each new `invocation.ref` must pass CAP1 **at the enforcement
  venue chosen above** — not "in CI" (CAP1 is inert there).
- **CAP2 (coverage / anti-omission)** — flag actionable entrypoints with no owning
  capability. Hardened from the review:
  - **Positive inclusion signal, not "all scripts minus exemptions."** Enumerating
    every `[project.scripts]` entry and subtracting an exempt-list makes the
    exempt-list the de-facto spec and is noisy by construction (`custodian-doctor`
    and `custodian-multi` both are scripts; only one is a capability). Define a
    positive marker instead — e.g. a `[tool.capabilities]`/pyproject annotation or
    a declared entrypoints namespace — so CAP2 flags only *declared-actionable*
    entrypoints lacking a capability. "Executor entrypoints" have **no enumerable
    source** today (the only `executor` notion is `invocation.kind: executor`
    inside the registry itself — circular); scope CAP2 to the positive-marked set.
  - `coverage_exempt` must be **drift-checked**: an exempt entry naming a script
    that no longer exists is flagged stale (mirror doctor's `exclude_paths`
    stale-glob warning) so it can't silently mask a future gap.
  - Dormant behind `audit.capabilities.coverage_enforce` (in-detector early
    return). **Note:** unlike CAP1, CAP2 reads the repo's OWN pyproject, so it is
    fully live in that repo's single-repo CI once enabled — opting a repo in is a
    standing CI obligation (every new declared-actionable entrypoint → catalog or
    exempt before merge). Treat each `coverage_enforce: true` as an explicit,
    repo-by-repo gated flip, separate from authoring the data.

## Phase 3 — Edge reality-binding (DESCOPED — mostly already enforced)
The review showed CAP3-as-originally-imagined is largely empty: `validated_by`
and `requires` compile to repo_id edges already enforced at RepoGraph load;
exactly-one-`owns` is already enforced; none can fire post-load.
- The **only** genuinely unchecked edge is `produces` — RepoGraph explicitly
  excludes `PRODUCES` from repo validation ("target is an artifact identifier,
  not a repo"), and **there is no artifact-kind registry** anywhere to resolve it
  against (`audit_report`, `gc_report` are free-text). So a `produces` check is
  unfalsifiable until an artifact-kind vocabulary exists.
- **Therefore:** Phase 3 reduces to "(a) define an artifact-kind registry, then
  (b) CAP3 validates `produces` against it." (a) is a real sub-project; (b) is
  trivial after. If `validated_by`-as-detector-reference is genuinely wanted (it
  is NOT what the schema means today — VALIDATES targets a repo), that is a
  **RepoGraph schema change**, called out as net-new design, not a Custodian
  detector. Until (a) lands, Phase 3 is deferred; do not ship an empty CAP3.

## Detector wiring recipe (corrected)
module under `audit_kit/detectors/` + entry in `build_capability_detectors()`
(picked up by both `cli/runner.py` and doctor's `known_ids` automatically) +
in-detector early-return on the enable flag + disposition-matrix row + positive
**and** negative control tests + a dormancy test (CAP1 precedent). No
`_KNOWN_AUDIT_KEYS` change for nested `capabilities.*` sub-flags.

## Phases 4–6 (GATED — separate operator go-ahead required)
- **Phase 4 — operative routing:** OC/SwitchBoard/CoreRunner consume the registry
  for dispatch; `routing.preferred_lane` promoted to operative behind a feature
  flag + unregistered-capability fallback. HIGH RISK — makes the registry
  load-bearing for execution; a registry typo becomes a dispatch failure. Its own
  arc; never on an autonomous campaign with low-risk legibility work.
- **Phase 5 — private-repo capabilities:** authored in the PrivateManifest
  registry; CAP1/2 resolve against private repos via `registry_repo`; boundary
  artifact keeps private names out of public surfaces (B1). Deferred per standing
  constraint.
- **Phase 6 — lifecycle & onboarding:** deprecation detection (retired capability
  with no code → flag); schema-version bump policy; artifact-kind registry (also
  unblocks Phase 3); "how to add a capability" guide.

## Resolved decisions (adversarial pass, 2026-06-16)
Each was put through an independent code-grounded adversarial analysis. Two of
the three "Phase 2–3 detectors" came back **don't build** — which simplifies the
remaining roadmap to: build ONE gate (the Direction-A CAP1 venue), then populate.

1. **CAP1 enforcement venue → SPLIT GATE.** Cross-repo refs break in two
   directions, each authored in a different repo: **(B)** an owning repo
   (OC/CL/Custodian) renames a symbol a ref points at — *already enforced for
   free* by that repo's existing pre-push (`custodian-multi --repos $repo_root`
   resolves the ref against the local sibling registry; CAP1 fires). **(A)** a
   registry edit in PlatformManifest points a ref at another repo's code — the
   real gap; PM's own pre-push owns no capability so it checks nothing. **Fix:**
   a **PM-side gate that runs CAP1 across the bounded owning set (exactly 3
   public repos: custodian, operations_center, context_lifecycle) with those
   repos checked out**, implemented in **PM CI with an explicit bounded
   multi-repo checkout** (the local pre-push is advisory pre-flight only — it
   fails *open* on an incomplete local workspace, so it cannot be the hard gate).
   REJECTED: all-22-repo sibling-checkout CI (cost ×22, only 3 own capabilities,
   still validates the wrong PM ref) and an OC dispatch sweep (single-repo →
   CAP1-inert today, and Plane-advisory → never blocks before merge). This gate
   is the **prerequisite for Phase 2 population.**
2. **CAP2 (coverage detector) → DON'T BUILD.** The registry holds 3 entries after
   ~18 months; omission is ~0/quarter, low-cost, and self-announcing (an
   unregistered capability is *invisible*, not *broken* — the operator who wants
   to route to it notices and registers it). The fleet has ~55 `[project.scripts]`
   (OC alone ~40, almost all internal tooling) → an enumerate-and-subtract CAP2
   is ~37 false positives per run; the exempt-list becomes the de-facto spec —
   exactly the "noisy check" smell Custodian's disposition matrix *retires*. A
   positive marker just moves "forgot to register" to "forgot to annotate" (and
   has zero fleet precedent); the "invert it" option literally *is* CAP1. **Build
   nothing now.** Revisit a *non-blocking, fleet-side advisory report* (never in a
   repo's single-repo CI) only if the registry crosses ~15–20 entries OR a real
   omission incident occurs.
3. **Artifact-kind registry / CAP3 `produces` → DEFER.** `produces` has **zero
   consumers** (not even serialized into the node projection); validating a
   write-only field is gold-plating — the "read-models rot silently" principle
   has no teeth without a reader. A full producer/consumer registry is maximal
   infra for a non-consumed field; even the cheap closed-enum option couples
   capability authoring (data) to RepoGraph releases (code) on the vocabulary
   *least* suited to closure (artifacts are an open, fleet-defined set). **Defer
   until a real consumer reads `produces`** — Phase 4 routing or a dependency
   graph — which will also dictate the correct vocabulary shape (enum vs. full
   registry). CAP3 stays unbuilt until then.

**Net reshaped roadmap:** (1) ✅ DONE — Direction-A PM-side CAP1 gate shipped
(`.github/workflows/capability-refs.yml`: on a `capabilities.yaml` change, checks
out the 3 owning repos + runs `custodian-multi --only CAP1`; proven by clean pass
+ negative control). → (2) ✅ DONE (first wave) — Phase 2 population: 6 added (9
total) covering the major fleet actions owned by the 3 gate-enforced repos
(custodian_autofix, fleet_audit_dispatch, spec_campaign,
autonomous_board_execution, console_reconcile, session_anchor); every ref
gate-verified. Internal tooling excluded per the inclusion principle. Extending
to RepoGraph/PlatformManifest/OperatorConsole-owned capabilities is a bounded
follow-up (opt those repos into CAP1 + add to the gate's owning set). → CAP3 and
CAP2 deferred behind explicit triggers above.
