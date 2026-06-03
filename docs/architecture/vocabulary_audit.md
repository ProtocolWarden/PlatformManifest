# Vocabulary Audit

This audit classifies the current PlatformManifest vocabulary against the
expanded role: platform topology, entity ontology, and visibility projection
layer.

## Classification

| Vocabulary | Classification | Notes |
| --- | --- | --- |
| `ManifestKind` | Already ontology-level | Declares manifest slot: platform, project, work scope, local. |
| `Visibility` | Visibility-related | Current values are `public` and `private`; unknown visibility fails closed at loader validation. |
| `Source` | Projection/provenance-related | Tracks whether a node or edge came from platform, project, or work scope. |
| `RepoNode.repo_id` | Already ontology-level | Stable entity id for repository nodes. |
| `RepoNode.canonical_name` | Already ontology-level | Human canonical name. |
| `RepoNode.kind` | Already ontology-level | Optional ontology kind, defaulting to `Repository`. |
| `RepoNode.owner` | Already ontology-level | Optional owner boundary for platform, project, or organization. |
| `RepoNode.scope` | Already ontology-level | Optional scope boundary for platform, project, or work scope. |
| `RepoNode.metadata` | Visibility-related | Structured descriptive metadata; public projection must allow or redact fields by policy. |
| `RepoNode.public_alias` | Projection-related | Disclosure-safe label for a repository identity. |
| `RepoNode.github_url` | Visibility-related | Public manifests may expose public URLs only. |
| `RepoNode.runtime_role` | Already ontology-level | High-level role only; must not become runtime invocation config. |
| `RepoEdge` | Already ontology-level | Queryable relationships between repository entities. |
| `RepoEdgeType.depends_on_contracts_from` | Already ontology-level | References protocol contract ownership without copying schemas. |
| `RepoEdgeType.dispatches_to` | Already ontology-level | Captures caller to orchestrator/backend relationship. |
| `RepoEdgeType.routes_through` | Already ontology-level | Captures routing/lane-selection dependency. |
| `RepoEdgeType.bundles_assets_from` | Already ontology-level | Captures artifact producer/consumer dependency. |
| Local annotation fields | Implementation-specific | `local_path`, `local_port`, `env_file`, `endpoint_override`, `cache_path`, `gpu_required`, and `runtime_hints` are local-only and forbidden in public platform manifests. |
| CxRP contract names | Belongs elsewhere | PlatformManifest may reference CxRP but must not own CxRP schemas. |
| RxP invocation names | Belongs elsewhere | PlatformManifest may reference RxP but must not own RxP schemas. |

## Gap Analysis

The current model is repository-graph first. It now carries the minimum
generic ontology fields needed for repository entities:

```text
repo_id        -> id
kind           -> kind
canonical_name -> name
visibility     -> visibility
owner/scope    -> owner/scope
RepoEdge       -> relationships
metadata       -> metadata
```

Future model work should add first-class non-repository entities only when
there is a concrete consumer query for them. Candidate entities include
`Manifest`, `Artifact`, `Run`, `Audit`, `Evidence`, `Binding`,
`VisibilityPolicy`, `ProjectionRule`, `RedactionRule`,
`MirrorRelationship`, and `SupersetRelationship`.

## Keep Elsewhere

These concepts must stay in their owning repositories:

* CxRP owns execution/routing contract semantics.
* RxP owns runtime invocation semantics.
* OperationsCenter owns governance and orchestration implementation.
* CoreRunner owns backend runtime invocation behavior.
* PlatformDeployment owns deployment and hosting behavior.
* Custodian owns leak and hygiene detector implementation.

PlatformManifest may point at those components as entities or relationships,
but it does not absorb their internal schemas or runtime code.
