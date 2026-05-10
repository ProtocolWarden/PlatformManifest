# Contributing to PlatformManifest

PlatformManifest is the canonical repo map for the platform: who exists, what they're called (and were called), and how they relate. It is intentionally small — a Python package, a YAML file, a CLI, and tests.

## Before You Start

- Check open issues to avoid duplicate work
- For changes to the repo map (`data/repo_graph.yaml`) — open an issue first; map changes ripple to OperationsCenter, SwitchBoard, and OperatorConsole impact queries
- For changes to the edge vocabulary (new `RepoEdgeType` value) — confirm a real query needs it; v1 vocabulary is intentionally minimal

## Development Setup

```bash
git clone https://github.com/ProtocolWarden/PlatformManifest.git
cd PlatformManifest
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

Requires Python 3.11+.

## Running Tests

```bash
.venv/bin/python -m pytest
```

## Project Structure

```
src/platform_manifest/
  __init__.py              # public API
  models.py                # RepoNode / RepoEdge / RepoGraph / RepoEdgeType
  loader.py                # YAML loader + bundled-data resolver
  cli.py                   # `platform-manifest` typer app
  data/
    repo_graph.yaml        # canonical platform repo map
tests/
  test_repo_graph.py
```

## Architectural Constraints

PlatformManifest describes the platform; it does not run it. Contributions must not:

- Add execution, dispatch, or routing logic (belongs in OperationsCenter / SwitchBoard / ExecutorRuntime)
- Add per-deployment configuration (belongs in each consumer repo's `<repo>.local.yaml`)
- Add fuzzy matching, scoring, or inferred edges — the map is explicit, fail-fast, and operator-authored

## Pull Requests

- Keep PRs focused — one concern per PR
- YAML changes: include the rationale (new repo, alias retirement, edge correction) in the PR description
- New `RepoEdgeType` values must come with a real consumer query that needs them
- Update `README.md` if the public API changes

## Commit Style

| Prefix | Use for |
|--------|---------|
| `feat:` | new node, new edge type, new public API |
| `fix:` | corrections to the repo map or loader behavior |
| `refactor:` | internal restructure, no behavior change |
| `docs:` | documentation only |
| `test:` | test additions or fixes |
| `chore:` | tooling, CI, dependency updates |

## Code of Conduct

This project follows the [Contributor Covenant v2.1](CODE_OF_CONDUCT.md). By participating you agree to uphold its standards.
