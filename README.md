# PlatformManifest

Public graph instance and projection publisher for the platform.

Read-only context for OperationsCenter planning, SwitchBoard lane decisions, and OperatorConsole displays. One source of truth so disclosure-safe projection labels and contract-impact queries match across consumers.

`PlatformManifest` now consumes shared ontology/topology/projection semantics
from `RepoGraph` instead of owning that vocabulary itself.
RepoGraph defines the graph language. It does not own graph instances.

## What this repo is

- A Python package (`platform_manifest`) exposing the public graph loader and projection tooling
- The bundled platform manifest at `src/platform_manifest/data/repo_graph.yaml`
- A read-only CLI: `platform-manifest list / resolve / upstream / downstream / impact`

## What this repo is not

- A deployment config store. Per-consumer local config (Plane URLs, team_executor settings, etc.) stays in each consumer repo with its own `<repo>.example.yaml` + gitignored `<repo>.local.yaml`.
- A runtime registry. CoreRunner owns runner registration; PlatformManifest only describes which repos play which platform roles.

## Quick start

```bash
pip install -e .
```

```python
from platform_manifest import load_default_repo_graph
graph = load_default_repo_graph()
graph.resolve("OperationsCenter")
```

CLI:

```bash
platform-manifest list
platform-manifest resolve OperationsCenter
platform-manifest impact cxrp
```

## Architecture

A bundled YAML at `src/platform_manifest/data/repo_graph.yaml` declares the
public graph instance. `RepoGraph` owns the reusable semantics: ontology,
topology, projection, and boundary-artifact vocabulary. `PlatformManifest`
imports those definitions, validates public graph data against them, and
publishes public-safe projections for downstream consumers.

## Edge vocabulary (v1)

| edge | meaning |
|---|---|
| `depends_on_contracts_from` | consumer → contract-owning repo |
| `dispatches_to` | caller → orchestrator |
| `routes_through` | orchestrator → router/lane selector |

Add new edge types only when a real query needs them.

## Public API

```python
from platform_manifest import (
    load_default_repo_graph,
    load_repo_graph,
    RepoGraph,
    RepoNode,
)

graph = load_default_repo_graph()
graph.resolve("OperationsCenter")
graph.affected_by_contract_change("cxrp")  # → [OC, SB, OperatorConsole]
graph.who_dispatches_to("core_runner") # → [OperationsCenter]
```

## Multi-repo work scope — `WorkScopeManifest` (v0.9+)

When several repos compose into one OperationsCenter work scope, author
a `WorkScopeManifest` (`manifest_kind: work_scope`). Each constituent
keeps its own `ProjectManifest`; the work scope explicitly includes them:

```yaml
manifest_kind: work_scope
manifest_version: "1.0.0"

includes:
  - name: ProjectA
    project_manifest_path: ../ProjectA/topology/project_manifest.yaml
  - name: ProjectB
    project_manifest_path: ../ProjectB/topology/project_manifest.yaml

repos: {}   # rare — the work scope may also declare its own
edges: []   # cross-suite edges (Source.WORK_SCOPE provenance)
```

The loader recurses included projects and applies their nodes/edges
before the work scope's own. Collisions (duplicate repo_id with platform
OR with a sibling include) are configuration errors. Cycles are detected
and rejected. `OperationsCenter` points at the work-scope manifest via
`work_scope_manifest_path` and gets the merged whole.

Worked example: see `examples/work_scope/`.

> **v1.0.0**: `manifest_kind: project` with `includes:` is rejected.
> Multi-repo composition is exclusively the role of
> `manifest_kind: work_scope`. (Migrated from? One-line change:
> `manifest_kind: project` → `manifest_kind: work_scope`.)

## CLI

```
platform-manifest list
platform-manifest resolve OperationsCenter
platform-manifest impact cxrp

# Validate a manifest against its JSON schema + loader rules.
# Auto-detects manifest_kind; pass --expected to enforce the slot.
# Project manifests are validated in composition with the bundled
# platform base (override with --against PATH).
platform-manifest validate path/to/project_manifest.yaml    --expected project
platform-manifest validate path/to/work_scope_manifest.yaml --expected work_scope
platform-manifest validate path/to/local_manifest.yaml --json   # CI-friendly

# Show the merged EffectiveRepoGraph — what OC actually consumes.
# Composes platform + (project XOR work_scope) + local layers exactly as
# OperationsCenter.repo_graph_factory does at runtime.
platform-manifest effective \
    --project path/to/project_manifest.yaml \
    --local   path/to/local_manifest.yaml
platform-manifest effective \
    --work-scope path/to/work_scope_manifest.yaml \
    --local      path/to/local_manifest.yaml
platform-manifest effective --json   # machine-readable

# Generate a public-safe projection from private/effective input.
platform-manifest project-public \
    --project path/to/project_manifest.yaml \
    --local   path/to/local_manifest.yaml \
    --output  public_manifest.json

# Emit the visibility policy descriptor Custodian can scan against.
platform-manifest custodian-policy
```

CI-friendly: exit 0 = clean, 1 = validation failed, 2 = bad invocation.
Pass `--json` to get a structured report consumable by automation.

## Install

```
pip install -e .          # development
pip install -e .[dev]     # with pytest + ruff
```

Consumer repos depend on it via:

```
"platform-manifest @ git+https://github.com/ProtocolWarden/PlatformManifest.git"
```

## License

GNU Affero General Public License v3.0 or later (AGPL-3.0-or-later) — see [LICENSE](LICENSE).
