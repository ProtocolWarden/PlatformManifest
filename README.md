# PlatformManifest

Canonical repo map for the platform: who exists, what they're called (and were called), and how they relate.

Read-only context for OperationsCenter planning, SwitchBoard lane decisions, and OperatorConsole displays. One source of truth so legacy → canonical name resolution and contract-impact queries match across consumers.

## What this repo is

- A Python package (`platform_manifest`) exposing the repo map model + loader
- The bundled platform manifest at `src/platform_manifest/data/repo_graph.yaml`
- A read-only CLI: `platform-manifest list / resolve / upstream / downstream / impact`

## What this repo is not

- A deployment config store. Per-consumer local config (Plane URLs, kodo settings, etc.) stays in each consumer repo with its own `<repo>.example.yaml` + gitignored `<repo>.local.yaml`.
- A runtime registry. ExecutorRuntime owns runner registration; PlatformManifest only describes which repos play which platform roles.

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
graph.resolve("ControlPlane")              # → OperationsCenter (legacy alias)
graph.affected_by_contract_change("cxrp")  # → [OC, SB, OperatorConsole]
```

## CLI

```
platform-manifest list
platform-manifest resolve ControlPlane
platform-manifest impact cxrp
```

## Install

```
pip install -e .          # development
pip install -e .[dev]     # with pytest + ruff
```

Consumer repos depend on it via:

```
"platform-manifest @ git+https://github.com/Velascat/PlatformManifest.git"
```

## License

[Apache-2.0](LICENSE).
