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
  ExecutorRuntime, and PlatformDeployment.
- [architecture/vocabulary_audit.md](architecture/vocabulary_audit.md) —
  Classification of current manifest vocabulary as ontology-level,
  visibility-related, projection-related, implementation-specific, or owned
  elsewhere.

## Verification

- [verification/manifest_system.md](verification/manifest_system.md) —
  Verification spec for the manifest composition system: edge resolution,
  asset producer/consumer graph, privacy boundaries, and the test
  scenarios that validate end-to-end correctness.
