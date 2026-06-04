# Verification Spec — Repo Graph Primitive and Layered Manifest System

**Status:** Verified (current shipped surface — PM v1.0.0).

## Purpose

Verify that the repo graph primitive and manifest system are correct, safe, and operationally useful.

This verification covers:

1. `PlatformManifest`
2. `PrivateManifest`
3. `ProjectManifest`
4. `WorkScopeManifest`
5. `LocalManifest`
6. `EffectiveRepoGraph`
7. `OperationsCenter` consumption
8. `SwitchBoard` boundary safety
9. CI/schema validation
10. Operator wiring and diagnostics

---

# Core Invariant

```text
PlatformManifest + PrivateManifest + (ProjectManifest xor WorkScopeManifest) + LocalManifest = EffectiveRepoGraph
```

The merged graph must let `OperationsCenter` reason about public platform repos,
private managed projects, and the currently selected project or work scope
without leaking private topology details into public manifests.

---

# Terminology

## PlatformManifest

Public reusable manifest.

Contains only public platform repos and public-safe relationships.

## PrivateManifest

Private platform superset.

Contains private managed projects, private repositories, and private-only
relationships. The shape is owned by PlatformManifest; the data may live in a
separate private-manifest repository.

## ProjectManifest

Project-specific extension manifest.

Contains project-scoped repos and edges, or acts as a compatibility shell
manifest that points operators at the private-manifest layer.

## WorkScopeManifest

Scoped work overlay.

Contains work-item or suite-specific topology overlays for a single effective
composition.

## LocalManifest

Machine-specific manifest.

Contains only local wiring annotations and runtime overlays for existing nodes.

## EffectiveRepoGraph

Runtime merged graph produced from:

```text
PlatformManifest → PrivateManifest → (ProjectManifest xor WorkScopeManifest) → LocalManifest
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
| work_scope  | work_scope (PM v0.9.0+) |
| local       | local                  |

The `project` and `work_scope` slots are mutually exclusive — exactly one of them participates in any single composition. See V16 for the multi-repo work-scope shape.

### Tests

* Passing a `ProjectManifest` as `base` fails.
* Passing a `LocalManifest` as `project` fails.
* Passing a `PlatformManifest` as `local` fails.
* Passing a `ProjectManifest` as `work_scope` fails.
* Passing a `WorkScopeManifest` as `project` fails.
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

### Projection helper

`to_public_manifest_dict(graph)` emits a public PlatformManifest-shaped
dictionary from an EffectiveRepoGraph. It keeps only public nodes,
public-to-public edges, and schema-allowed public fields. Local annotations
and private project details have no output slot.

The `platform-manifest project-public` CLI wraps the same helper:

```bash
platform-manifest project-public \
  --project path/to/project_manifest.yaml \
  --local path/to/local_manifest.yaml \
  --output public_manifest.json
```

By default the command validates generated output against the public
PlatformManifest schema.

### Projection tests

* Private project nodes are absent from public projections.
* Edges touching private nodes are absent from public projections.
* Local-only fields such as `local_path`, `env_file`, and `runtime_hints`
  are absent from public projections.
* Private URLs and internal paths are absent from public projections.
* Generated public projections validate as `manifest_kind: platform`.

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
* CI proves public projection output validates against the PlatformManifest
  schema.

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

## V11a — Public Projection CLI

### Requirement

`platform-manifest project-public` must derive public output from composed
private/effective input instead of requiring separately authored public
manifests.

### Expected behavior

* Accepts `--project` or `--work-scope`, mutually exclusive by composition
  rules.
* Accepts `--local` to prove local fields are dropped.
* Emits JSON to stdout by default.
* Writes JSON to `--output` when provided.
* Validates generated output by default.
* Exits `2` for composition errors.

### Tests

* Private node names and private URLs do not appear in CLI output.
* Local paths and env files do not appear in CLI output.
* Output file mode writes valid JSON.
* Invalid private/effective input exits with a composition error.

---

## V12 — OperationsCenter Wiring

### Requirement

`OperationsCenter` must consume `EffectiveRepoGraph`, not own the manifest source of truth.

### Settings block

OC's `PlatformManifestSettings` carries two mutually-exclusive second-layer fields. Set exactly one:

```yaml
# single-project mode
platform_manifest:
  enabled: true
  project_slug: my-project
  project_manifest_path: /home/dev/Documents/GitHub/<managed-repo>/topology/project_manifest.yaml
  local_manifest_path:   /home/dev/Documents/GitHub/<managed-repo>/topology/local_manifest.yaml
```

```yaml
# work-scope mode (PM v0.9.0+)
platform_manifest:
  enabled: true
  project_slug: media-product-suite
  work_scope_manifest_path: /home/dev/Documents/GitHub/MediaProductSuite/topology/work_scope_manifest.yaml
  local_manifest_path:      /home/dev/Documents/GitHub/MediaProductSuite/topology/local_manifest.yaml
```

A Pydantic `model_validator` enforces XOR at config load: setting both `project_manifest_path` and `work_scope_manifest_path` raises a clear "mutually exclusive" error before any manifest is read.

### Tests

* No config produces platform-only graph.
* Configured project manifest produces graph with project node.
* Configured work-scope manifest produces graph with included projects' nodes (Source.PROJECT) plus any work-scope-declared edges (Source.WORK_SCOPE).
* `project_manifest_path` and `work_scope_manifest_path` both set raises a configuration error at `load_settings()`.
* Configured local manifest annotates nodes in either mode.
* Warning is logged when manifest load fails — graph degrades to `None` gracefully (OC startup never blocks).
* OC does not silently treat a failed project/work-scope load as success.

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
* platform/project/work-scope/local manifest path resolution
* runtime dispatch classes
* Plane task propagation
* SourceRegistry ownership

### Enforcement

OC ships a static denylist at `tools/boundary/switchboard_denylist.py` that scans the SwitchBoard source tree for forbidden symbol names. The denylist is forward-looking — it includes symbols that don't yet exist in SB so accidental adoption fails the boundary check. Currently covers:

* ER-001…ER-004 primitives (`SwarmCoordinator`, `LifecycleRunner`, `RunMemoryIndexWriter`, `RepoGraphLoader`, `RepoGraphIndexer`, etc.)
* Runtime dispatch (`CoreRunner`, `RuntimeRunner`, `SubprocessRunner`, `RuntimeInvocation`, `RuntimeResult`)
* Fork management (`SourceRegistry`)
* Manifest/composition symbols (PM v0.9.0+): `load_repo_graph`, `load_effective_graph`, `load_default_repo_graph`, `PlatformManifestSettings`, `build_effective_repo_graph`, `build_effective_repo_graph_from_settings`, `WorkScopeManifest`, `ManifestKind`

### Tests

* Static denylist check prevents `SwitchBoard` from importing manifest composition internals.
* Static denylist check prevents runtime dispatch ownership leaking into `SwitchBoard`.
* Static denylist check prevents WorkScopeManifest authority leaking into `SwitchBoard`.
* Lane/backend selection tests still work with repo context as plain input.

---

## V14 — PlatformDeployment Boundary

### Requirement

`PlatformDeployment` may own LocalManifest *path discovery*, not platform or project manifest ownership.

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

* PlatformDeployment returns local manifest path or `None` — no YAML parsing.
* OperationsCenter consumes returned path.
* PlatformDeployment does not merge manifests.

---

## V14a — Custodian Visibility Policy Descriptor

### Requirement

PlatformManifest must provide Custodian with stable detector inputs without
owning Custodian's detector implementation.

### Expected behavior

`platform-manifest custodian-policy` emits JSON containing:

```text
policy_owner
policy
unknown_visibility
unknown_field_policy
forbidden_public_fields
checks[]
```

### Tests

* Policy owner is `PlatformManifest`.
* Unknown visibility is declared as private.
* Unknown field policy is declared as drop.
* Forbidden public fields include private URLs, internal paths, private
  bindings, private artifact locations, restricted relationship edges, and
  runtime hints.
* Check IDs include private repo name detection and relationship projection
  policy validation.
* Custodian PMV detectors fail a leaky public manifest and pass a clean
  public projection.
* The PMV detector implementation is contributed by PlatformManifest via
  `platform_manifest.custodian_native:build_custodian_detectors`, not owned by
  Custodian core.

---

## V15 — Single-Repo Project Layout

### Requirement

If one repo is the project, its ProjectManifest may live inside that repo.

### Expected layout

```text
<managed-repo>/
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

## V16 — Multi-Repo Work Scope (PM v0.9.0+, hard-enforced v1.0.0+)

### Requirement

If many repos together form one OperationsCenter work scope, author a `WorkScopeManifest` (`manifest_kind: work_scope`) in a dedicated shell repo. Each constituent keeps its own `ProjectManifest`; the work-scope manifest composes them via explicit `includes:`.

### Migration history

* PM v0.8.0 introduced multi-repo composition via `manifest_kind: project` + `includes:` (the "project-shell" pattern).
* PM v0.9.0 promoted multi-repo composition to a first-class `manifest_kind: work_scope` with its own schema and provenance (`Source.WORK_SCOPE`); the earlier project-shell shape still loaded but emitted `DeprecationWarning`.
* PM v1.0.0 removed the earlier compatibility entirely. `manifest_kind: project` with `includes:` is rejected at the schema layer (the `includes` field is gone from `project_manifest.schema.json`) and at the loader layer (with an explicit migration-hint `RepoGraphConfigError`).

### Expected layout

```text
ProjectSuiteManifest/
  topology/
    work_scope_manifest.yaml      # composes constituent ProjectManifests
    local_manifest.example.yaml
    local_manifest.yaml           # gitignored

ProjectCore/                      # each constituent keeps its own ProjectManifest
ProjectAssets/
ProjectWorker/
```

### `WorkScopeManifest` shape

```yaml
manifest_kind: work_scope
manifest_version: "1.0.0"

platform_manifest:
  name: PlatformManifest
  version_constraint: ">=1.0,<2.0"

includes:
  - name: ProjectCore
    project_manifest_path: ../ProjectCore/topology/project_manifest.yaml
  - name: ProjectAssets
    project_manifest_path: ../ProjectAssets/topology/project_manifest.yaml

repos: {}    # rare — usually empty
edges: []    # cross-suite edges declared here carry Source.WORK_SCOPE
```

### Composition rules

| Rule | Behavior on violation |
| ---- | --------------------- |
| Two included projects declare the same `repo_id` | Hard fail — `'X' already declared by an included project` |
| Included project tries to redefine a platform `repo_id` | Hard fail |
| Work-scope manifest tries to redefine a platform `repo_id` | Hard fail |
| Work-scope edge between two platform nodes | Hard fail |
| Cycle (A includes B includes A) | Hard fail — `cycle detected` |
| Excessive nesting (>4 deep by default) | Hard fail — `depth exceeded` |
| Edge to/from a sibling included project | **Allowed** — the whole point |

### Provenance

* Included project's nodes/edges → `Source.PROJECT`.
* Work-scope manifest's own nodes/edges → `Source.WORK_SCOPE`.
* Local annotations applied on top of either.

### Tests

* `WorkScopeManifest` with one include validates and composes.
* `WorkScopeManifest` with multiple sibling includes composes; nodes from each appear.
* Included project node colliding with platform fails.
* Sibling included-project repo_id collision fails.
* Cross-suite edge between sibling included projects succeeds and carries `Source.WORK_SCOPE` on edges declared by the work-scope manifest itself.
* `manifest_kind: project` with `includes:` is rejected (schema + loader, post-v1.0.0).
* Wrong-slot loading fails both ways: `work_scope` rejected when passed via `project=` slot and vice versa.
* `load_effective_graph(project=, work_scope=)` with both set raises mutual-exclusion error.
* No-implicit-discovery: sibling `decoy.yaml` and `topology/project_manifest.yaml`-named decoys in the same directory are NOT auto-included.

### Constraint

Cross-project imports occur only via the explicit `includes:` field of a `WorkScopeManifest`. Implicit cross-references — loading manifest A and somehow seeing manifest B's nodes — are not supported. The loader does not scan sibling directories or glob.

---

## V17 — Contract Impact Consumer

### Requirement

Repo graph must have at least one real consumer proving value.

### Current consumers (PM v0.8.0)

| Query | Walks edge type | Use case |
| ----- | --------------- | -------- |
| `affected_by_contract_change(repo_id)` | `depends_on_contracts_from` | "what breaks if CxRP/RxP changes?" |
| `who_dispatches_to(repo_id)`            | `dispatches_to`             | "who would notice if OC went down?" |
| `who_consumes_assets_of(repo_id)`       | `bundles_assets_from`       | "what breaks if our asset publisher changes its bundle format?" |

### Tests

* Contract repo change identifies public consumers.
* Contract repo change identifies private project consumers when ProjectManifest is configured.
* Contract repo change impact summary includes public/private counts.
* Platform-only graph does not report private project nodes.
* Configured project graph reports private impact when appropriate.
* `who_consumes_assets_of` returns the right consumers from a synthetic graph. Note: no real `bundles_assets_from` edge is currently authored in any tracked manifest — the edge type stands for when a real producer/consumer asset relationship surfaces.

---

## V18 — Operator Diagnostics

### Requirement

Operators must be able to tell whether manifest wiring is active.

### Required signals

At minimum, logs or doctor output should show:

* PlatformManifest path/version
* selected composition mode: `disabled` | `platform_only` | `project` | `work_scope`
* ProjectManifest path if mode is `project`
* WorkScopeManifest path if mode is `work_scope`
* LocalManifest path if configured
* graph node count
* graph edge count
* source counts: platform / project / work_scope
* visibility counts: public / private
* in `work_scope` mode: per-include breakdown (name, path, nodes_contributed, edges_contributed)
* warnings/errors

### Tests

* Successful wiring prints or records graph summary.
* Failed wiring prints or records actionable error.
* Platform-only fallback is explicit, not silent.
* `operations-center-graph-doctor` exits 0 on success / 1 on graph_built=False / 2 on bad invocation.
* `mode` field correctly distinguishes the four states.
* Per-include breakdown surfaces in JSON output as `includes: [{name, path, nodes_contributed, edges_contributed}]` and in human output as a bulleted list.
* Per-include errors are captured per-entry — one bad include doesn't blank the whole report.
* Visibility counts surface as `nodes_by_visibility: {public: N, private: M}` in JSON; human output renders a `nodes_by_visibility:` line.
* Installed `platform-manifest` package version surfaces in the report (resolves via `importlib.metadata`); reads `(unknown)` if discovery fails.

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
