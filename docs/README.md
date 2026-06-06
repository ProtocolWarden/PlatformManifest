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
