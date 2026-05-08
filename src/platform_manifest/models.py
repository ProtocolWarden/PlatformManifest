# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Velascat
"""Repo Graph models — RepoNode, RepoEdge, RepoGraph + manifest metadata."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ManifestKind(str, Enum):
    """Trust-level slot a manifest occupies in the composition pipeline."""

    PLATFORM = "platform"
    PROJECT = "project"
    LOCAL = "local"


class Visibility(str, Enum):
    """Trust classification for a single repo node."""

    PUBLIC = "public"
    PRIVATE = "private"


class Source(str, Enum):
    """Provenance: which manifest contributed a node or edge after merge.

    LocalManifest cannot introduce nodes or edges (per design Rule 3), so
    it does not appear here — local annotations attach to nodes that came
    from PLATFORM or PROJECT.
    """

    PLATFORM = "platform"
    PROJECT = "project"


class RepoEdgeType(str, Enum):
    """v1 edge vocabulary. Add new values only when a real query needs them."""

    DEPENDS_ON_CONTRACTS_FROM = "depends_on_contracts_from"
    DISPATCHES_TO = "dispatches_to"
    ROUTES_THROUGH = "routes_through"


class RepoGraphConfigError(ValueError):
    """Raised when a manifest is malformed or violates a merge rule."""


# Allowlist for fields a LocalManifest may set on an existing node.
LOCAL_ANNOTATION_FIELDS: frozenset[str] = frozenset({
    "local_path",
    "local_port",
    "env_file",
    "endpoint_override",
    "cache_path",
    "gpu_required",
    "runtime_hints",
})


@dataclass(frozen=True)
class RepoNode:
    """One repo. Architectural fields come from PlatformManifest or
    ProjectManifest; local annotation fields are populated only by a
    LocalManifest at composition time."""

    repo_id: str
    canonical_name: str
    visibility: Visibility = Visibility.PUBLIC
    legacy_names: tuple[str, ...] = ()
    github_url: str | None = None
    runtime_role: str | None = None
    # Provenance — set by the loader at merge time. Defaults to PLATFORM
    # so programmatic construction in tests stays trivial.
    source: Source = Source.PLATFORM
    # Local annotation fields — only LocalManifest may set these.
    local_path: str | None = None
    local_port: int | None = None
    env_file: str | None = None
    endpoint_override: str | None = None
    cache_path: str | None = None
    gpu_required: bool | None = None
    # Pairs because the dataclass is frozen and dict isn't hashable.
    runtime_hints: tuple[tuple[str, "str | int | float | bool"], ...] = ()


@dataclass(frozen=True)
class RepoEdge:
    src: str  # repo_id
    dst: str  # repo_id
    type: RepoEdgeType
    source: Source = Source.PLATFORM


@dataclass(frozen=True)
class ManifestHeader:
    """Top-of-file metadata every manifest carries."""

    manifest_kind: ManifestKind
    manifest_version: str


@dataclass
class RepoGraph:
    """A manifest's parsed nodes + edges. The merged runtime view returned
    by ``load_effective_graph`` carries the same shape — provenance is
    annotated on each node/edge via ``source``."""

    nodes: dict[str, RepoNode] = field(default_factory=dict)  # keyed by repo_id
    edges: tuple[RepoEdge, ...] = ()
    # name index built at construction time: lowercased canonical & legacy → repo_id
    _name_index: dict[str, str] = field(default_factory=dict, repr=False)

    @classmethod
    def build(
        cls,
        nodes: list[RepoNode],
        edges: list[RepoEdge],
    ) -> "RepoGraph":
        node_map: dict[str, RepoNode] = {}
        name_index: dict[str, str] = {}
        for node in nodes:
            if node.repo_id in node_map:
                raise RepoGraphConfigError(f"duplicate repo_id: {node.repo_id}")
            node_map[node.repo_id] = node
            for alias in (node.canonical_name, *node.legacy_names):
                key = alias.lower()
                if key in name_index and name_index[key] != node.repo_id:
                    raise RepoGraphConfigError(
                        f"name '{alias}' maps to both "
                        f"'{name_index[key]}' and '{node.repo_id}'"
                    )
                name_index[key] = node.repo_id
        for edge in edges:
            if edge.src not in node_map:
                raise RepoGraphConfigError(
                    f"edge {edge.type.value} references unknown src '{edge.src}'"
                )
            if edge.dst not in node_map:
                raise RepoGraphConfigError(
                    f"edge {edge.type.value} references unknown dst '{edge.dst}'"
                )
        return cls(nodes=node_map, edges=tuple(edges), _name_index=name_index)

    # -- queries ---------------------------------------------------------

    def list_nodes(self) -> list[RepoNode]:
        """All known repos in stable canonical-name order."""
        return sorted(self.nodes.values(), key=lambda n: n.canonical_name)

    def resolve(self, name: str) -> RepoNode | None:
        """Resolve a canonical or legacy name to its node. Case-insensitive."""
        repo_id = self._name_index.get(name.lower())
        if repo_id is None:
            return None
        return self.nodes[repo_id]

    def upstream(self, repo_id: str) -> list[RepoNode]:
        """Direct upstream nodes — i.e., nodes this repo points to via its outgoing edges."""
        if repo_id not in self.nodes:
            raise KeyError(repo_id)
        targets = {e.dst for e in self.edges if e.src == repo_id}
        return [self.nodes[t] for t in sorted(targets)]

    def downstream(self, repo_id: str) -> list[RepoNode]:
        """Direct downstream nodes — i.e., nodes that point to this repo."""
        if repo_id not in self.nodes:
            raise KeyError(repo_id)
        sources = {e.src for e in self.edges if e.dst == repo_id}
        return [self.nodes[s] for s in sorted(sources)]

    def affected_by_contract_change(self, repo_id: str) -> list[RepoNode]:
        """Repos that depend on `repo_id` via DEPENDS_ON_CONTRACTS_FROM."""
        if repo_id not in self.nodes:
            raise KeyError(repo_id)
        consumers = {
            e.src
            for e in self.edges
            if e.dst == repo_id and e.type == RepoEdgeType.DEPENDS_ON_CONTRACTS_FROM
        }
        return [self.nodes[c] for c in sorted(consumers)]

    def who_dispatches_to(self, repo_id: str) -> list[RepoNode]:
        """Repos that dispatch work to `repo_id` via DISPATCHES_TO.

        Answers operational questions like 'who would notice if
        OperationsCenter went down?' or 'which orchestrators send work
        to ExecutorRuntime?'. Promotes the existing ``dispatches_to``
        edge from informational metadata to a first-class queryable.

        Returned in stable canonical-name order. Raises ``KeyError``
        if ``repo_id`` is unknown — same convention as the other
        directional queries.
        """
        if repo_id not in self.nodes:
            raise KeyError(repo_id)
        dispatchers = {
            e.src
            for e in self.edges
            if e.dst == repo_id and e.type == RepoEdgeType.DISPATCHES_TO
        }
        return [self.nodes[d] for d in sorted(dispatchers)]


# ---------------------------------------------------------------------------
# Effective graph alias
# ---------------------------------------------------------------------------

# After v0.3 composition, the merged result is a RepoGraph whose nodes
# carry `source` and (for local-annotated platform/project nodes)
# populated local_* fields. We expose the alias to make consumer code
# self-document — an EffectiveRepoGraph is a RepoGraph that has been
# through composition.
EffectiveRepoGraph = RepoGraph
