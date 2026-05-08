# Verification Spec — Repo Graph Primitive and Three-Layer Manifest System

**Status:** Verified (current shipped surface — PM v0.8.0).

## Purpose

Verify that the repo graph primitive and manifest system are correct, safe, and operationally useful.

This verification covers:

1. `PlatformManifest`
2. `ProjectManifest`
3. `LocalManifest`
4. `EffectiveRepoGraph`
5. `OperationsCenter` consumption
6. `SwitchBoard` boundary safety
7. CI/schema validation
8. Operator wiring and diagnostics

---

# Core Invariant

```text
PlatformManifest + ProjectManifest + LocalManifest = EffectiveRepoGraph
```

The merged graph must let `OperationsCenter` reason about public platform repos and the currently selected project (or suite of projects) without leaking private project details into public manifests.

---

# Terminology

## PlatformManifest

Public reusable manifest.

Contains only public platform repos.

## ProjectManifest

Project-specific manifest.

Contains repos and edges for one project — or, when used as a **shell manifest**, references multiple sub-project manifests via `includes:` (added in PM v0.8.0).

Can be public or private.

## LocalManifest

Machine-specific manifest.

Contains only local wiring annotations for existing nodes.

## EffectiveRepoGraph

Runtime merged graph produced from:

```text
PlatformManifest → ProjectManifest (with optional sub-project includes) → LocalManifest
```

---

# Verification Categories

## V1 — Manifest Kind Validation

### Requirement

The loader must enforce `manifest_kind` by slot.

### Expected behavior

| Loader slot | Required manifest_kind |
| ----------- | ---------------------- |
| base        | platform               |
| project     | project                |
| local       | local                  |

### Tests

* Passing a `ProjectManifest` as `base` fails.
* Passing a `LocalManifest` as `project` fails.
* Passing a `PlatformManifest` as `local` fails.
* Correct kinds load successfully.

### Expected error shape

```text
RepoGraphConfigError: expected manifest_kind='platform' for base manifest; got manifest_kind='project'.
```

---

## V2 — Visibility Boundary

### Requirement

Every repo node must carry explicit visibility.

Allowed values:

```text
public
private
```

### PlatformManifest rules

* May contain only `visibility: public` nodes.
* Must reject `visibility: private` nodes.

### ProjectManifest rules

* May contain `visibility: public` or `visibility: private` nodes.
* May reference platform nodes.
* Must not redefine platform nodes.

### LocalManifest rules

* Must not change visibility.

### Tests

* `PlatformManifest` with private node fails.
* `ProjectManifest` with private node succeeds.
* `LocalManifest` that sets `visibility` fails.
* Effective graph preserves visibility from source manifests.

### Expected error shape

```text
RepoGraphConfigError: PlatformManifest may only contain public nodes; repo_id='video_foundry_api' has visibility='private'.
```

---

## V3 — PlatformManifest Public Safety

### Requirement

`PlatformManifest` must be safe to publish publicly.

### Forbidden fields/content

* private repo names
* customer repo names
* private GitHub URLs
* local paths
* env file paths
* machine names
* secrets
* developer-specific ports
* closed-source service topology

### Tests

* Schema rejects `local_path` in `PlatformManifest`.
* Schema rejects `env_file` in `PlatformManifest`.
* Schema rejects `endpoint_override` in `PlatformManifest`.
* Schema rejects `visibility: private` in `PlatformManifest`.

### Human review question

```text
Could this file be open-sourced without leaking private information?
```

If no, verification fails.

---

## V4 — ProjectManifest Attachment Rules

### Requirement

`ProjectManifest` may attach to the platform, but may not modify the platform.

### Allowed

* Add project nodes.
* Add edges from project nodes to platform nodes.
* Add edges from platform nodes to project nodes only when the project is explicitly the target of platform dispatch/orchestration.
* Add edges between project nodes.

### Forbidden

* Redefine platform nodes.
* Change platform node metadata.
* Remove platform edges.
* Add edges where both endpoints are platform nodes.

### Tests

* Project node addition succeeds.
* Project-to-platform edge succeeds.
* Project-to-project edge succeeds.
* Project redefinition of `operations_center` fails.
* Project-added `operations_center -> source_registry` edge fails if both are platform nodes.

### Expected error shapes

```text
RepoGraphConfigError: ProjectManifest cannot redefine platform repo_id='operations_center'.
```

```text
RepoGraphConfigError: ProjectManifest cannot add platform-to-platform edge operations_center -> source_registry.
```

---

## V5 — LocalManifest Allowlist

### Requirement

`LocalManifest` may annotate existing nodes only with local-machine fields.

### Allowed fields

```text
local_path
local_port
env_file
endpoint_override
cache_path
gpu_required
runtime_hints
```

### Forbidden examples

* `canonical_name`
* `visibility`
* `runtime_role`
* `owned_contracts`
* `consumed_contracts`
* `github_url`

### Tests

* `local_path` annotation succeeds.
* `gpu_required` annotation succeeds.
* `canonical_name` annotation fails.
* `visibility` annotation fails.
* LocalManifest referencing unknown repo fails.

### Expected error shape

```text
RepoGraphConfigError: LocalManifest field 'canonical_name' is not allowed; allowed fields are local_path, local_port, env_file, endpoint_override, cache_path, gpu_required, runtime_hints.
```

---

## V6 — Merge Semantics

### Requirement

Manifest composition must be deterministic.

### Order

```text
PlatformManifest → ProjectManifest (and any included sub-projects) → LocalManifest
```

### Rules

* Platform nodes load first.
* Project nodes are added second. When the project manifest declares `includes:`, sub-project nodes/edges are applied first, then the including project's own.
* Local annotations are applied last.
* Duplicate repo IDs between platform and project — or between two sibling sub-projects — are errors.
* Duplicate edges with same `(from, to, type)` are deduped.
* Different edge types between same repos are allowed.

### Tests

* Merged graph has all platform nodes.
* Merged graph has project nodes.
* Merged graph has local annotations.
* Duplicate project/platform repo ID fails.
* Duplicate edge dedupes.
* Same endpoints with different edge types remain distinct.

---

## V7 — EffectiveRepoGraph Provenance

### Requirement

Merged nodes/edges should preserve loader-created provenance for debugging.

### Provenance values

```text
source: platform | project
```

`LocalManifest` does not introduce nodes or edges (per design Rule 3 — it only annotates), so it does not appear in the provenance enum. Local-annotated nodes retain their original `source` (platform or project) and surface their local annotations via the populated local-only fields (`local_path`, `local_port`, etc.).

This field is produced by the loader, not authored by users.

### Tests

* Platform node has `source = platform`.
* Project node has `source = project`.
* Locally annotated platform node retains `source = platform`; its `local_path` etc. are populated.
* Provenance appears in debug/doctor output and in `platform-manifest effective` rendering.
* Provenance is not required in authored YAML.

---

## V8 — Edge Vocabulary and Future Expansion Rule

### Requirement

Edge vocabulary is closed-by-default and expanded only via the explicit four-step rule.

### Current edge types (PM v0.8.0)

| Edge type | Introduced |
| --------- | ---------- |
| `depends_on_contracts_from` | v1 (initial) |
| `dispatches_to`             | v1 (initial) |
| `routes_through`            | v1 (initial) |
| `bundles_assets_from`       | v0.7.0 (added under expansion rule) |

### Future expansion rule (mandatory four-step process)

Adding a new edge type requires all four:

1. A real consumer query that needs it.
2. A `PlatformManifest` minor version bump.
3. Schema update on `platform_manifest.schema.json` + `project_manifest.schema.json`.
4. Tests covering the new type.

### Tests

* Valid edge types pass schema validation.
* Unknown edge type fails (schema enum).
* `ProjectManifest` cannot invent ad-hoc new edge types — they must match the schema's enum.
* Each shipped edge type has at least one consumer query (`affected_by_contract_change`, `who_dispatches_to`, `who_consumes_assets_of`).

### Expected error shape (unknown type)

```text
RepoGraphConfigError: edge #N has unknown type 'invented_edge_type'; allowed: ['depends_on_contracts_from', 'dispatches_to', 'routes_through', 'bundles_assets_from'].
```

---

## V9 — Version Constraints

### Requirement

Project manifests must declare the compatible PlatformManifest version.

### Syntax

Use Python/PEP 440 specifier syntax.

Examples:

```text
>=1.0,<2.0
>=1.2,<2.0
==1.4.3
```

### Tests

* Valid PEP 440 constraint passes.
* Invalid npm-style constraint such as `^1.0` fails.
* ProjectManifest requiring incompatible PlatformManifest version fails.

---

## V10 — Schema Packaging and CI Validation

### Requirement

Schemas live in the public `PlatformManifest` repo and are shipped as package data.

### Required schemas

```text
src/platform_manifest/schemas/platform_manifest.schema.json
src/platform_manifest/schemas/project_manifest.schema.json
src/platform_manifest/schemas/local_manifest.schema.json
```

### CI checks

PlatformManifest repo:

* validates bundled `data/platform_manifest.yaml`
* validates examples
* verifies schema files are included in package data

Consumer repos:

* validate `topology/project_manifest.yaml` against `project_manifest.schema.json`
* validate `topology/local_manifest.example.yaml` against `local_manifest.schema.json` if present

### Tests

* `importlib.resources.files("platform_manifest.schemas")` can locate schemas.
* CI fails on malformed manifest.
* CI fails on private node in PlatformManifest.

---

## V11 — Validate CLI

### Requirement

`platform-manifest validate <path>` gives fast operator feedback.

### Expected behavior

* Auto-detects manifest kind from `manifest_kind`.
* Supports explicit expected kind via `--expected`.
* For project manifests, validates in composition with the bundled platform base by default; `--against PATH` overrides.
* Returns exit code `0` on success, `1` on validation failure, `2` on bad invocation.
* Prints clear structured errors.
* `--json` mode emits machine-readable `ValidationReport`.

### Tests

* Valid platform manifest passes.
* Valid project manifest passes (composed against platform base).
* Valid local manifest passes (schema only).
* Wrong expected kind fails.
* Malformed YAML fails.
* Schema violation fails.

---

## V12 — OperationsCenter Wiring

### Requirement

`OperationsCenter` must consume `EffectiveRepoGraph`, not own the manifest source of truth.

### Settings block

Example local config:

```yaml
platform_manifest:
  enabled: true
  project_slug: video-foundry
  project_manifest_path: /home/dev/Documents/GitHub/VideoFoundry/topology/project_manifest.yaml
  local_manifest_path: /home/dev/Documents/GitHub/VideoFoundry/topology/local_manifest.yaml
```

### Tests

* No config produces platform-only graph.
* Configured project manifest produces graph with project node.
* Configured local manifest annotates nodes.
* Warning is logged when manifest load fails — graph degrades to `None` gracefully (OC startup never blocks).
* OC does not silently treat a failed project load as success.

### Operational verification

A configured project run shows:

```text
graph: 10+ nodes, 13+ edges
ProjectNode: source=project, visibility=private, local_path=..., gpu_required=True
OperationsCenter: source=platform, local_path=...
```

---

## V13 — SwitchBoard Boundary

### Requirement

`SwitchBoard` may receive repo graph context, but must not own manifest loading, merging, runtime dispatch, or project wiring.

### Forbidden in SwitchBoard

* manifest loaders
* effective graph composition
* platform/project/local manifest path resolution
* runtime dispatch classes
* Plane task propagation
* SourceRegistry ownership

### Tests

* Static denylist check prevents `SwitchBoard` from importing manifest composition internals.
* Static denylist check prevents runtime dispatch ownership leaking into `SwitchBoard`.
* Lane/backend selection tests still work with repo context as plain input.

---

## V14 — WorkStation Boundary

### Requirement

`WorkStation` may own LocalManifest *path discovery*, not platform or project manifest ownership.

### Allowed

* expose local manifest path via `discover_local_manifest(slug)`
* resolve user-scoped local manifest location (XDG, env override, repo-root convention)
* report local runtime availability
* report local paths/endpoints

### Forbidden

* owning PlatformManifest
* owning ProjectManifest
* deciding orchestration policy
* mutating repo graph architecture
* reading or validating manifest YAML content

### Tests

* WorkStation returns local manifest path or `None` — no YAML parsing.
* OperationsCenter consumes returned path.
* WorkStation does not merge manifests.

---

## V15 — Single-Repo Project Layout

### Requirement

If one repo is the project, its ProjectManifest may live inside that repo.

### Expected layout

```text
VideoFoundry/
  topology/
    project_manifest.yaml
    local_manifest.example.yaml
    local_manifest.yaml       # gitignored
```

### Tests

* CWD/convention discovery finds `topology/project_manifest.yaml` when appropriate.
* Explicit path always wins over convention discovery.
* `local_manifest.yaml` is gitignored or otherwise not committed if machine-specific.

---

## V16 — Multi-Repo Project Layout (PM v0.8.0+)

### Requirement

If many repos together form one project, use one project shell/manifest repo.

### Expected layout

```text
ProjectSuiteManifest/
  topology/
    project_manifest.yaml         # declares includes:
    local_manifest.example.yaml
    local_manifest.yaml           # gitignored

ProjectCore/                      # constituent repos keep their own manifests
ProjectWorker/
ProjectAssets/
```

### Shell manifest shape

```yaml
manifest_kind: project
manifest_version: "1.0.0"

platform_manifest:
  name: PlatformManifest
  version_constraint: ">=0.8,<1.0"

includes:
  - name: ProjectCore
    project_manifest_path: ../ProjectCore/topology/project_manifest.yaml
  - name: ProjectAssets
    project_manifest_path: ../ProjectAssets/topology/project_manifest.yaml

repos: {}
edges: []
```

### Composition rules across the shell

| Rule | Behavior on violation |
| ---- | --------------------- |
| Two sub-projects declare the same `repo_id` | Hard fail — `'X' already declared by an included sub-project` |
| Sub-project tries to redefine a platform `repo_id` | Hard fail |
| Cycle (A includes B includes A) | Hard fail — `cycle detected` |
| Excessive nesting (>4 deep by default) | Hard fail — `depth exceeded` |
| Sub-project edge between two platform nodes | Hard fail |
| Sub-project edge to/from a sibling sub-project | **Allowed** — this is the whole point |

### Tests

* Shell manifest with one include validates and composes.
* Shell manifest with multiple sibling includes composes; nodes from each appear.
* Sub-project node colliding with platform fails.
* Sibling sub-project repo_id collision fails.
* Self-include cycle fails.
* Two-step cycle fails.
* Depth-exceeded fails.
* Cross-suite edge between sibling sub-projects succeeds.

### Constraint

Project-to-project imports occur only via the explicit `includes:` declaration. Implicit cross-references (loading manifest A and somehow seeing manifest B's nodes) are not supported.

---

## V17 — Contract Impact Consumer

### Requirement

Repo graph must have at least one real consumer proving value.

### Current consumers (PM v0.8.0)

| Query | Walks edge type | Use case |
| ----- | --------------- | -------- |
| `affected_by_contract_change(repo_id)` | `depends_on_contracts_from` | "what breaks if CxRP/RxP changes?" |
| `who_dispatches_to(repo_id)`            | `dispatches_to`             | "who would notice if OC went down?" |
| `who_consumes_assets_of(repo_id)`       | `bundles_assets_from`       | "what breaks if Warehouse changes its asset format?" |

### Tests

* Contract repo change identifies public consumers.
* Contract repo change identifies private project consumers when ProjectManifest is configured.
* Contract repo change impact summary includes public/private counts.
* Platform-only graph does not report private project nodes.
* Configured project graph reports private impact when appropriate.
* `who_consumes_assets_of` returns the right consumers from a synthetic graph and from the real VF→Warehouse edge.

---

## V18 — Operator Diagnostics

### Requirement

Operators must be able to tell whether manifest wiring is active.

### Required signals

At minimum, logs or doctor output should show:

* PlatformManifest path/version
* ProjectManifest path if configured
* LocalManifest path if configured
* graph node count
* graph edge count
* source counts: platform/project
* warnings/errors

### Tests

* Successful wiring prints or records graph summary.
* Failed wiring prints or records actionable error.
* Platform-only fallback is explicit, not silent.
* `operations-center-graph-doctor` exits 0 on success / 1 on graph_built=False / 2 on bad invocation.

---

# Manual Verification Checklist

Use this after implementation or after wiring a new project.

## PlatformManifest

* [ ] Contains only public nodes
* [ ] Contains no local paths
* [ ] Contains no private repo names
* [ ] Validates in CI
* [ ] Ships schemas as package data
* [ ] Has versioned release

## ProjectManifest

* [ ] Has `manifest_kind: project`
* [ ] Pins PlatformManifest version using PEP 440 syntax
* [ ] Contains project-specific nodes
* [ ] Does not redefine platform nodes
* [ ] Does not add platform-to-platform edges
* [ ] Validates in CI
* [ ] (If a shell) `includes:` paths resolve cleanly with no cycles or platform-id collisions

## LocalManifest

* [ ] Has `manifest_kind: local`
* [ ] Contains only allowlisted local fields
* [ ] Does not change canonical identity
* [ ] Does not change visibility
* [ ] Is gitignored if machine-specific

## EffectiveRepoGraph

* [ ] Loads platform nodes
* [ ] Loads project nodes
* [ ] Applies local annotations
* [ ] Preserves provenance
* [ ] Dedupes duplicate edges
* [ ] Rejects invalid collisions

## OperationsCenter

* [ ] Reads PlatformManifest from dependency at the latest verified version
* [ ] Reads configured ProjectManifest
* [ ] Reads configured LocalManifest
* [ ] Emits visible graph summary
* [ ] Uses graph in contract impact analysis

## SwitchBoard

* [ ] Receives repo context only as input
* [ ] Does not load manifests
* [ ] Does not merge graphs
* [ ] Does not dispatch runtime work

---

# Definition of Verified

The repo graph primitive and three-layer manifest system are verified when:

1. All schemas validate in CI.
2. `platform-manifest validate` catches malformed manifests before runtime.
3. `PlatformManifest` cannot contain private nodes or local fields.
4. `ProjectManifest` cannot redefine platform nodes or reshape platform internals.
5. `LocalManifest` can only annotate local-machine fields.
6. `EffectiveRepoGraph` merge behavior is deterministic and tested.
7. `OperationsCenter` can load and consume a real private project manifest.
8. `SwitchBoard` remains a lane/backend selector only.
9. Contract impact analysis (and the other consumer queries) prove the graph has real consumers.
10. Operators can see whether manifest wiring is active.
11. Each new edge type beyond v1 satisfies the four-step expansion rule.
12. Multi-repo project shells compose with collision/cycle/depth/edge rules enforced.

---

# Deferred Verification

These remain intentionally out of scope for the current verification:

* **Cross-repo task chaining** as a *production-active* feature. The machinery is shipped (R5: `propagation/` library + `operations-center-propagate` entrypoint + post-merge hook reference + `propagation-links` inspection CLI). It is `enabled: false` by default. Verification of fired-vs-skipped propagation behavior, dedup correctness across version bumps, and trust-boundary preservation requires real production traffic — this should get its own verification spec when an operator policy enables it.
* **New edge types beyond the four currently shipped** (`depends_on_contracts_from`, `dispatches_to`, `routes_through`, `bundles_assets_from`). Each future addition must satisfy V8's four-step expansion rule and gets verified at that time.
* **Project-to-project imports outside the explicit `includes:` declaration**. Implicit cross-references are not on the roadmap.
* **Web UI for propagation chains**. CLI-only suffices until operator demand surfaces.
* **`suite_id` for stable identities independent of repo path**. PM v1+ minor when multiple suites need shared identity.

These should get their own verification specs when implemented.
