# SPDX-License-Identifier: SSPL-1.0
# Copyright (C) 2026 Velascat
"""platform_manifest — canonical platform repo map.

Treats repos as graph nodes with canonical identity + legacy-name resolution
+ direct upstream/downstream queries. Read-only context for OperationsCenter
planning and SwitchBoard lane-decision input.

Public API:
  load_repo_graph(path: Path) -> RepoGraph
  load_default_repo_graph() -> RepoGraph
  RepoGraph.resolve(name) -> RepoNode | None
  RepoGraph.upstream(repo_id) -> list[RepoNode]
  RepoGraph.downstream(repo_id) -> list[RepoNode]
  RepoGraph.affected_by_contract_change(repo_id) -> list[RepoNode]
"""

from .loader import (
    default_config_path,
    load_default_repo_graph,
    load_repo_graph,
)
from .models import (
    RepoEdge,
    RepoEdgeType,
    RepoGraph,
    RepoGraphConfigError,
    RepoNode,
)

__all__ = [
    "RepoEdge",
    "RepoEdgeType",
    "RepoGraph",
    "RepoGraphConfigError",
    "RepoNode",
    "default_config_path",
    "load_default_repo_graph",
    "load_repo_graph",
]
