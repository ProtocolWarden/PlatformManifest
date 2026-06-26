# Log
## 2026-06-26 — Adversarial round 2: control plane vs anchor

Second adversarial pass on `docs/architecture/control_plane_and_anchor.md`
(three attackers: buildability, internal-consistency, framing). The first two
*converged* on the biggest hole, which is a strong signal. Applied (triaged,
with one adversary overclaim rejected):
- **Named the restorer.** The rewrite said the verifier "mutates nothing" yet
  drift was "auto-restored" — an unnamed write-capable actor (the most dangerous
  component) absent from the role table and TCB. Added it as a role + a threat
  bullet (re-verifies the signature, declarative-only, in the audited TCB, on the
  dead-man's switch).
- **Deploy-only-from-signed-reference.** The enforce-vs-change rule wasn't
  runtime-decidable (`max_turns=50` vs `500`: identical bytes, only intent
  differs). Fix: make the signed reference the sole writer, so "drift" can only
  mean unauthorized divergence — no intent-classifier needed. Behavioral
  (LLM-agent) drift has no signed artifact → degrades to quarantine-and-flag;
  restore-rate bounded + loop detection.
- **Per-axis monotonicity, no netting** (bundling a tighten + a loosen defeated
  the old rule); **v0-axiom + predecessor-signs-successor** for the
  self-referential policy (self-reference ≠ self-grounding); **public-key pinning
  + off-infra signing key** (crypto relocates the bootstrap, doesn't remove it);
  **dead-man's switch terminus = human attention**, alarm consumer must be
  failure-domain-disjoint; **verifier self-repair via deploy-from-signed**
  (resolves immutability vs degrade-never-halt); `[check: ref]` has two failure
  modes (staleness vs silent-wrong-check) needing two mitigations.
- **Framing:** separation of *authority*, not necessarily address space (an
  in-process corrector with no write-path to its own reference already satisfies
  separation of powers — keeps the deep target access the fleet's debug history
  needs); added a property-vs-implementation caution and a trust-grounding-axis
  disclaimer (the threat axis — untrusted-input ingestion — is the reviewer-
  incident edge); a proportionality section (build the MVP anchor now, sequence
  hardening). REJECTED the adversary's "the 5 blocked tasks are infra chores →
  gate false-positive" — OAuth-refresh touches the credential anchor itself,
  circuit-breaker/infra-robustness touch executor self-healing; the gate is
  mostly correct, which supports the thesis. Still a sketch; no control-plane
  code yet.

## 2026-06-26 — Adversarial refinement: control plane vs anchor

Expanded and hardened `docs/architecture/control_plane_and_anchor.md` after an
adversarial pass (two grounding agents + one red-team). Material corrections to
the committed sketch: (1) **Provenance fix** — the precise `require_review`
policy log line the draft quoted was a *reconstruction*, not a real artifact;
the locally-verifiable lease record (`.context/sessions/s-2026-06-08-af23/.../
l-64cc79e2…yaml`) actually reads `failure_category: policy_blocked` /
`failure_reason: 'execution blocked by policy: blocked on retry'`. Replaced the
fabricated quote with the real one and downgraded the claim. (2) **Regress
reframing** — dropped "the chain *terminates* at an anchor needing no corrector"
(false: it hides the verifier+scheduler actors); replaced with "it *grounds* in
an inert, human-signed **trust anchor** (PKI sense) leaving a small **trusted
computing base** we audit by inspection." (3) **Reconciliation** of "no human in
the per-correction loop" vs "control-plane changes need review" via the
enforce-vs-change rule (the human changes the reference, not enforces it; the
control plane self-heals drift but not its own spec). (4) Added a **threat
model** (anchor capture, signature forgery, envelope creep + monotonicity/
self-referential closure, staleness/dead-man's switch) and an **availability vs.
authority** section (no-bootstrap-deadlock, degrade-never-halt). (5) Demoted
"empirically revealed the anchor surface" (circular) to "reconfirms a
human-drawn boundary"; promoted **separation of powers** to the thesis.
(6) Backed off "factor the two controllers into one component, two configs"
(wrong-abstraction at N=2) to "extract the shared harness; keep audit-monitor
and convergence-driver as distinct policies." (7) Added a terminology warning
disambiguating this doc's **trust anchor** from ContextLifecycle session
*anchoring* (`CL_ANCHOR`). Updated the README index entry to match. Still a
sketch for operator review; no control-plane code yet.

## 2026-06-26 — Design sketch: control plane vs anchor

Added `docs/architecture/control_plane_and_anchor.md` (+ README index entry).
Fixes the vocabulary the topology discussion kept tripping on: data plane /
control plane / anchor are a single correction chain, not layers stacked by
altitude. Documents the regress argument (the anchor cannot be a controller
without adding a turtle), the policy `require_review` gate that empirically
revealed the anchor surface (the fleet's own policy refused autonomous
self-modification of its control plane), and the two formalization moves — lift
the control plane out of OC into one component with two instances (VF, OC); keep
the anchor a minimal human-signed discipline, not a service. Sketch for operator
review; no control-plane code yet.

## 2026-06-16 — Phase 2 follow-up: 3 more owners (12 total) + gate expanded

Closed the population follow-up — capabilities owned by the other public repos:
repo_graph_projection (repograph, cli repograph), capability_registry_query
(platform_manifest, cli platform-manifest — the registry's own query surface),
context_bootstrap (operator_console, entrypoint
operator_console.bootstrap.build_resume_prompt). RepoGraph + OperatorConsole opted
into CAP1 (RepoGraph #7, OperatorConsole #69) and were added to the capability-refs
gate's owning set (now 5 cross-repo owners). PlatformManifest self-enforces its own
capability via registry_path (registry is in-repo; no sibling). Negative control:
breaking the repograph/operator_console refs fails CAP1 in those repos. 12
capabilities total; doctor --strict accepts the new `capabilities` keys.

## 2026-06-16 — Phase 2 population: 6 fleet capabilities (9 total)

Populated `capabilities.yaml` with the major operator-facing actions owned by the
3 gate-enforced repos: custodian_autofix (cli custodian-fix), fleet_audit_dispatch
+ spec_campaign + autonomous_board_execution (OC entrypoints), console_reconcile +
session_anchor (CL entrypoints). Internal tooling (calibration, fixtures, replay,
doctors, triage) excluded per the inclusion principle — fleet-meaningful actions
only. Every new invocation.ref verified by the Direction-A gate (CAP1 across the 3
owning repos: clean). Phase 1 consumer renders all 9 grouped by owner. Extending
to RepoGraph/PM/OperatorConsole owners needs those repos opted into CAP1 + added to
the gate (bounded follow-up). Updated test_capabilities seed set.

## 2026-06-16 — Decision 1 gate built: Direction-A CAP1 CI (capability plane)

Added `.github/workflows/capability-refs.yml` — the Direction-A enforcement venue
from the resolved decisions. On a `capabilities.yaml` change it checks out the 3
bounded owning repos (Custodian, OperationsCenter, ContextLifecycle) alongside the
PR's registry and runs `custodian-multi --only CAP1`, so a registry edit pointing
a ref at missing/renamed owner code fails at the repo where it was authored —
closing CAP1's single-repo-CI blind spot. Proven locally: clean pass + negative
control (break board_unblock's ref → OperationsCenter CAP1 fails). Direction-B
(owner renames a symbol) stays covered by that repo's own pre-push. Also ran
`cl reconcile prune --apply` (log 399→32, history archived to the private side) —
the proper archive+trim, replacing the inline trims I'd been doing.

## 2026-06-16 — Resolved the 3 capability-plane open decisions (adversarial)

Code-grounded adversarial analysis per decision; recorded in
`capability-plane-completion-spec.md`. (1) CAP1 venue → SPLIT GATE: owning-repo
pre-push already covers code-side breaks; add a PM-CI bounded multi-repo checkout
for registry-side breaks (the real gap, prerequisite for population). (2) CAP2
coverage detector → DON'T BUILD (3-entry registry, ~0 omissions; revisit advisory
past ~15–20). (3) artifact registry / CAP3 produces → DEFER (zero consumers).

## Recent Decisions

_Log significant choices here so they survive context resets._

| Decision | Rationale | Date |
|----------|-----------|------|
| Promote multi-repo composition to first-class `WorkScopeManifest` (manifest_kind: work_scope). v0.9.0 ships transitional support; project+includes still loads with DeprecationWarning. v1.0.0 will hard-fail. | Overloading `manifest_kind: project` for shells blurred the trust posture — a shell composes, a project describes. Distinct kind + schema + provenance (Source.WORK_SCOPE) prevents semantic drift and enables strict slot validation in OC settings. | 2026-05-08 |
| Ship worked examples in `examples/{single_project,work_scope}/` and validate them in CI. README + OC operator docs migrated to v0.9 vocabulary. | An operator authoring their first manifest needs a runnable starting point that's kept fresh by CI, not a copy-paste blob in markdown that rots. The examples pin v0.9 platform_manifest constraints, exercise both manifest kinds, and the CI step `validate-examples` ensures schema/loader changes can't silently break authoring guidance. | 2026-05-08 |
| Cut PM v1.0.0: hard-fail `manifest_kind: project` with `includes:` (R4). | Scan of all five sibling repos found zero authored legacy shells, so the gating criterion was already satisfied. Leaving the deprecation branch around just preserves ambiguity for future authors. v1.0.0 removes `includes` from the project schema (schema rejects at the field-validation layer), drops the deprecation warning in `_apply_project` and replaces it with an explicit migration-hint `RepoGraphConfigError` (catches direct loader callers that bypass schema), deletes `test_includes.py` (project-of-project recursion is no longer reachable; collision/composition rules are covered by `test_work_scope.py`), bumps example version_constraints to `>=1.0,<2.0`. | 2026-05-08 |
| Scrub Warehouse-as-asset-producer framing from PM artifacts. | The R7.2/R7.3 motivating example was wrong-semantics — Warehouse is developer/operator tooling (repo chunking, LLM context extraction), NOT a runtime artifact provider. a private downstream repo doesn't operationally consume Warehouse-produced artifacts. Audit confirmed the bad edge was never in any committed `topology/project_manifest.yaml` (a private downstream repo still pins `>=0.3,<1.0`, edge absent), but the framing fossilized in `models.py` docstring + `tests/test_repo_graph.py` node labels + `docs/verification/manifest_system.md`. Synthetic test labels switched to `GenericApi/GenericWorker/AssetPublisher`; docstring + verification doc reframed around generic "asset publisher"; verification doc carries an explicit retraction note. Edge type `BUNDLES_ASSETS_FROM` itself stands — keep until a real producer/consumer asset relationship surfaces. Mechanism stays correct; semantic interpretation corrected before the graph vocabulary fossilized around it. | 2026-05-08 |
| Add no-implicit-discovery invariant tests. | DoD audit caught that the verification spec's "loader does not scan sibling directories / does not glob" assertion was not explicitly covered. New `TestNoImplicitDiscovery` (2 cases) places sibling `decoy.yaml` + `topology/project_manifest.yaml`-named decoys alongside an explicitly-included manifest and proves they are NOT pulled in. Defense-in-depth against future "but it'd be convenient if it auto-discovered..." regression. | 2026-05-08 |

## Notes

_Free-form scratch. Clear periodically — old entries can be deleted once no longer relevant._

---

## Archived

_Archived completed history → `/home/dev/Documents/GitHub/PrivateManifest/archive/console/PlatformManifest/log-2026-06-04.md`_


## 2026-06-18 — wire visibility_scope fail-closed; delete load_default_capabilities

Ecosystem incomplete-integration remediation (combined PM change):
- WIRE: load_repo_graph now calls parse_visibility_scope(raw, path=path) to
  fail-closed on visibility at the load boundary (docs/inject/loader.md mandates
  this; the function existed but was never called — the genuine #313 gap).
  Positioned after the platform public-only + node-visibility checks so their
  specific errors fire first; this catches the remaining scope-ambiguous /
  invalid-scope cases. New test: load rejects an invalid visibility_scope even
  when all repos are public. (The audit flagged this as DELETE; the loader.md
  convention hook correctly flipped it to WIRE.)
- DELETE: load_default_capabilities (cached convenience mirror of
  load_capabilities, which prod uses via capabilities_cli). Rewrote the 3 seed-
  invariant tests to call load_capabilities() directly (preserve coverage, per
  the ToolAdapter/T1 lesson). Removed the unused _cached_default global.
289 tests green; ruff + audit (B2 env only) + doctor clean.
