# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 ProtocolWarden
"""platform_manifest — canonical platform repo map + composition.

Treats repos as graph nodes with canonical identity + legacy-name resolution
+ direct upstream/downstream queries. Three trust slots:

    PlatformManifest  — public, reusable
    ProjectManifest   — one project using the platform
    LocalManifest     — one machine's wiring for one project

The merged runtime view is an EffectiveRepoGraph.

Public API:
  load_default_repo_graph() -> RepoGraph
  load_repo_graph(path, *, expected_kind=PLATFORM) -> RepoGraph
  load_effective_graph(base, *, project=None, local=None) -> RepoGraph
  RepoGraph.resolve(name) -> RepoNode | None
  RepoGraph.upstream(repo_id) -> list[RepoNode]
  RepoGraph.downstream(repo_id) -> list[RepoNode]
  RepoGraph.affected_by_contract_change(repo_id) -> list[RepoNode]
"""

from .composition import load_effective_graph
from .loader import (
    default_config_path,
    load_default_repo_graph,
    load_repo_graph,
)
from .models import (
    EffectiveRepoGraph,
    LOCAL_ANNOTATION_FIELDS,
    ManifestHeader,
    ManifestKind,
    RepoEdge,
    RepoEdgeType,
    RepoGraph,
    RepoGraphConfigError,
    RepoNode,
    Source,
    Visibility,
)

__all__ = [
    "EffectiveRepoGraph",
    "LOCAL_ANNOTATION_FIELDS",
    "ManifestHeader",
    "ManifestKind",
    "RepoEdge",
    "RepoEdgeType",
    "RepoGraph",
    "RepoGraphConfigError",
    "RepoNode",
    "Source",
    "Visibility",
    "default_config_path",
    "load_default_repo_graph",
    "load_effective_graph",
    "load_repo_graph",
]
