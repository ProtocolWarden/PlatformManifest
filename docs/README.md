# PlatformManifest Documentation

Index for the `docs/` tree. The README at the repo root covers the
manifest system overview and usage; this directory holds longer-form
verification specs and design notes.

## Architecture

- [architecture/platformmanifest_ontology.md](architecture/platformmanifest_ontology.md) —
  PlatformManifest as platform ontology and visibility registry, including
  entity kinds, relationships, and the ontology responsibility split.
- [architecture/public_private_projection.md](architecture/public_private_projection.md) —
  Private superset to public projection semantics, redaction behavior, and
  projection test plan.
- [architecture/platform_topology.md](architecture/platform_topology.md) —
  Platform repo topology, OperationsCenter consumption, managed-project
  participation, and execution timeline.
- [architecture/control_plane_and_anchor.md](architecture/control_plane_and_anchor.md) —
  The data plane / control plane / verifier / restorer / trust-anchor distinction
  as a single correction chain grounded in **separation of powers**: why the
  regress *grounds* (in an inert, human-signed *trust anchor* plus a small audited
  TCB of verifier + scheduler + restorer) rather than terminating at a magic
  non-actor; *deploy-only-from-signed-reference* as the mechanism that makes
  "restore vs. change" decidable without an intent-classifier; a threat model
  (anchor capture, restorer compromise, signature forgery + the public-key
  bootstrap, per-axis monotonicity against envelope creep, the v0 axiom for
  self-referential policy, staleness vs. silent-wrong-check); availability vs.
  authority; and what to formalize — separate the *authority* (not necessarily the
  address space), extract a shared harness (don't over-unify the controllers at
  N=2), and build the minimum anchor now, sequencing the hardening.
- [architecture/visibility_boundary.md](architecture/visibility_boundary.md) —
  Visibility boundary between PlatformManifest, Custodian, OperationsCenter,
  CoreRunner, and PlatformDeployment.
- [architecture/vocabulary_audit.md](architecture/vocabulary_audit.md) —
  Classification of current manifest vocabulary as ontology-level,
  visibility-related, projection-related, implementation-specific, or owned
  elsewhere.
- [architecture/console-reconciliation.md](architecture/console-reconciliation.md) —
  Fleet-wide `.console/` source reconciliation: consolidate-before-prune
  discipline, the three-layer system (detectors / `cl reconcile` / private
  archive), and the adversarial refinement record. Implementation contract in
  [console-reconciliation-spec.md](architecture/console-reconciliation-spec.md);
  generated fleet status in
  [console-reconciliation-status.md](architecture/console-reconciliation-status.md).
- [architecture/private-manifest-role-generalization.md](architecture/private-manifest-role-generalization.md) —
  Design for generalizing the hardcoded private-manifest *instance* to a
  discovered *role* (N project private-manifests), with the staged,
  regression-aware migration plan.

- [architecture/cognition-memory-overview.md](architecture/cognition-memory-overview.md) —
  **the connecting document** for the cognition/memory architecture: the two
  cognition hosts + anchoring, the five-tier memory model and its transport
  semantics, cross-machine sync, the enforced knowledge lifecycle
  (capture → reconcile → promote → inject), and pointers into each deep spec.
  Start here to re-orient.
- [architecture/contextlifecycle-anchoring.md](architecture/contextlifecycle-anchoring.md) —
  How sessions in non-cognition-host repos anchor to their owning manifest via
  ContextLifecycle (`CL_ANCHOR`): hook enforcement tiers, the OperatorConsole
  pane shim, and the OC executor-backend `cl_wrap` lineage capture.

## Design drafts

- [architecture/context-injection-spec.md](architecture/context-injection-spec.md) —
  **DRAFT** design checkpoint for tiered memory & hook-based context injection:
  four-tier memory (hot/warm/cold/ephemeral), edit-time injection, the
  capture→consolidate lifecycle, and cross-repo publish-down. Not yet approved
  for build; the build is gated after the warm-injection phase.
- [architecture/context-injection-work-order.md](architecture/context-injection-work-order.md) —
  Phased build order for the spec above. Phase 0–2 (router engine, routes, leaf
  docs, tests) implemented and shipped dark; phases 3–5 gated.
- [architecture/capability-plane-completion-spec.md](architecture/capability-plane-completion-spec.md) —
  Completion spec (Phases 1–6) for the capability registry beyond v1, hardened
  against an adversarial review. Phase 1 (session-start Fleet-Capabilities
  consumer) shipped; Phase 2 (population + CAP2 anti-omission) and Phase 3 (CAP3,
  descoped to `produces` pending an artifact registry) specified; Phases 4–6
  gated. Records the CAP-inert-in-single-repo-CI enforcement-venue constraint.

- [architecture/oc-audit-and-pseudooperator-spec.md](architecture/oc-audit-and-pseudooperator-spec.md) —
  Grounded audit of OC + VF controllers with file:line receipts: verified role
  mapping (data/control/verifier/restorer/anchor vs real code), eight 🔴 defects
  (forgeable label bypass, fail-open containment, token-in-sandbox, VF
  timeout/locking, `audit_dispatch` gaps), PseudoOperator formalization plan
  (de-dup copy-paste controllers, activate inert config schema, move guardrails
  into code), restorer vs anchor distinction, and three-track build sequencing.
- [architecture/sandbox-token-hardening-spec.md](architecture/sandbox-token-hardening-spec.md) —
  Spec for replacing the long-lived OAuth `gho_` token forwarded into the bwrap
  sandbox with a per-task GitHub App installation token (1h TTL, repo-scoped,
  raw credential never in sandbox env). Covers approach, injection change,
  fine-grained PAT fallback, and sequencing relative to other OC hardening work.

## Verification

- [verification/manifest_system.md](verification/manifest_system.md) —
  Verification spec for the manifest composition system: edge resolution,
  asset producer/consumer graph, privacy boundaries, and the test
  scenarios that validate end-to-end correctness.

## Cognition Hosting

- [context-layout.md](context-layout.md) —
  `.context/` layout for hosting cognition state of anchored sessions
  (public-scope; per Phase 3 of PlatformDeployment ADR 0002).

## Forking + private overlay

- [forking-guide.md](forking-guide.md) —
  How to fork the platform and bootstrap your own private-manifest repo, boundary
  artifact publishing, and the secrets each consumer repo needs.
