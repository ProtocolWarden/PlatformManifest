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

## Design drafts

- [architecture/context-injection-spec.md](architecture/context-injection-spec.md) —
  **DRAFT** design checkpoint for tiered memory & hook-based context injection:
  four-tier memory (hot/warm/cold/ephemeral), edit-time injection, the
  capture→consolidate lifecycle, and cross-repo publish-down. Not yet approved
  for build; the build is gated after the warm-injection phase.

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
  How to fork the platform and bootstrap your own PrivateManifest, boundary
  artifact publishing, and the secrets each consumer repo needs.
