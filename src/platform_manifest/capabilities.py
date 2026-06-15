# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 ProtocolWarden
"""Read-model access to the platform capability registry.

Capabilities are authored in ``data/capabilities.yaml`` as a versioned
``capabilities`` document and compiled by RepoGraph into the canonical
node+edge graph. This module resolves the registry against the platform repo
map so that the owner / executes / requires / validates references are checked
against real repos at load time.

v1 is read-only: there is no authoring or mutation API here, only inspection.
``invocation.ref`` stays opaque — Custodian's CAP1 detector resolves it against
the owning repo's code in a separate plane.
"""

from __future__ import annotations

from importlib import resources
from pathlib import Path
from typing import Any

import yaml

from ._repograph import import_repograph
from .loader import load_default_repo_graph

_repograph = import_repograph("repograph")

CapabilityRegistry = _repograph.CapabilityRegistry
RepoGraphConfigError = _repograph.RepoGraphConfigError
_load_capability_registry = _repograph.load_capability_registry

_CAPABILITIES_FILENAME = "capabilities.yaml"


def default_capabilities_path() -> Path:
    """Path to the bundled capability registry document."""
    return Path(
        str(resources.files("platform_manifest") / "data" / _CAPABILITIES_FILENAME)
    )


def platform_repo_ids(graph: Any | None = None) -> set[str]:
    """The set of repo_ids known to the platform repo map.

    Used as ``known_repo_ids`` so capability edges that name a repo
    (owner/executes/requires/validates) fail closed when the repo is unknown.
    """
    graph = graph or load_default_repo_graph()
    return {node.repo_id for node in graph.list_nodes()}


def load_capabilities(
    path: Path | None = None,
    *,
    graph: Any | None = None,
    resolve_repos: bool = True,
) -> Any:
    """Load and compile the capability registry.

    *path* defaults to the bundled document. When *resolve_repos* is True
    (default) repo-targeting edges are checked against the platform repo map;
    pass False to compile without repo resolution (e.g. for a standalone file
    whose repos live in another manifest).
    """
    path = path or default_capabilities_path()
    if not path.exists():
        raise RepoGraphConfigError(f"capabilities file not found: {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise RepoGraphConfigError(f"capabilities root must be a mapping: {path}")
    known = platform_repo_ids(graph) if resolve_repos else None
    return _load_capability_registry(raw, known_repo_ids=known)


_cached_default: Any | None = None


def load_default_capabilities() -> Any:
    """Cached load of the bundled capability registry."""
    global _cached_default
    if _cached_default is None:
        _cached_default = load_capabilities()
    return _cached_default
