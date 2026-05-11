# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 ProtocolWarden
"""Repo Graph and ontology models for PlatformManifest."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ManifestKind(str, Enum):
    """Trust-level slot a manifest occupies in the composition pipeline."""

    PLATFORM = "platform"
    PRIVATE = "private"
    PROJECT = "project"
    WORK_SCOPE = "work_scope"
    LOCAL = "local"


class Visibility(str, Enum):
    """Trust classification for a single entity or relationship."""

    PUBLIC = "public"
    PRIVATE = "private"
    INTERNAL = "internal"
    RESTRICTED = "restricted"
    LOCAL = "local"


class ProjectionBehavior(str, Enum):
    """How an entity or relationship behaves when projected publicly."""

    PUBLIC_SAFE = "public_safe"
    PRIVATE_ONLY = "private_only"
    LOCAL_ONLY = "local_only"
    REDACT = "redact"
    REDACTED_PUBLIC_STUB = "redacted_public_stub"
    DROP_FROM_PUBLIC = "drop_from_public"


class Source(str, Enum):
    """Provenance: which manifest contributed a node or edge after merge."""

    PLATFORM = "platform"
    PRIVATE = "private"
    PROJECT = "project"
    WORK_SCOPE = "work_scope"


class EntityKind(str, Enum):
    """Constrained ontology vocabulary for repository-shaped entities."""

    REPOSITORY = "Repository"
    PROJECT = "Project"
    MANAGED_PROJECT = "ManagedProject"
    MANAGED_REPOSITORY = "ManagedRepository"
    PUBLIC_REPOSITORY = "PublicRepository"
    PRIVATE_REPOSITORY = "PrivateRepository"
    PROTOCOL_REPOSITORY = "ProtocolRepository"
    ARTIFACT_PRODUCER = "ArtifactProducer"
    DEPLOYMENT_LAYER = "DeploymentLayer"
    EXECUTION_BACKEND = "ExecutionBackend"
    MANIFEST = "Manifest"
    ARTIFACT = "Artifact"
    RUN = "Run"
    AUDIT = "Audit"
    EVIDENCE = "Evidence"
    BINDING = "Binding"
    VISIBILITY_POLICY = "VisibilityPolicy"
    PROJECTION_RULE = "ProjectionRule"
    REDACTION_RULE = "RedactionRule"
    MIRROR_RELATIONSHIP = "MirrorRelationship"
    SUPERSET_RELATIONSHIP = "SupersetRelationship"


class OntologyRelationshipKind(str, Enum):
    """First-class ontology relationship vocabulary."""

    PROJECTS_TO = "projects_to"
    REDACTS_FROM = "redacts_from"
    IMPLEMENTS = "implements"
    DOCUMENTS = "documents"
    ORCHESTRATES = "orchestrates"
    DEPLOYS = "deploys"
    HOSTS = "hosts"
    REFERENCES_SCHEMA_FROM = "references_schema_from"
    MANAGES = "manages"
    PRODUCES_ARTIFACTS_FOR = "produces_artifacts_for"
    CONSUMES_MANIFEST_FROM = "consumes_manifest_from"
    VALIDATES_WITH = "validates_with"
    LOADS_PLUGIN_FROM = "loads_plugin_from"


class RepoEdgeType(str, Enum):
    """Operational repo-graph edge vocabulary retained for compatibility."""

    DEPENDS_ON_CONTRACTS_FROM = "depends_on_contracts_from"
    DISPATCHES_TO = "dispatches_to"
    ROUTES_THROUGH = "routes_through"
    BUNDLES_ASSETS_FROM = "bundles_assets_from"


class RepoGraphConfigError(ValueError):
    """Raised when a manifest is malformed or violates a merge rule."""


MetadataValue = str | int | float | bool


LOCAL_ANNOTATION_FIELDS: frozenset[str] = frozenset({
    "local_path",
    "local_port",
    "env_file",
    "endpoint_override",
    "cache_path",
    "gpu_required",
    "runtime_hints",
})


def default_projection_behavior_for_visibility(
    visibility: Visibility,
) -> ProjectionBehavior:
    if visibility is Visibility.PUBLIC:
        return ProjectionBehavior.PUBLIC_SAFE
    if visibility is Visibility.LOCAL:
        return ProjectionBehavior.LOCAL_ONLY
    return ProjectionBehavior.DROP_FROM_PUBLIC


@dataclass(frozen=True)
class RepoNode:
    """One repository-shaped entity in PlatformManifest."""

    repo_id: str
    canonical_name: str
    visibility: Visibility = Visibility.PUBLIC
    legacy_names: tuple[str, ...] = ()
    github_url: str | None = None
    runtime_role: str | None = None
    kind: EntityKind = EntityKind.REPOSITORY
    owner: str | None = None
    scope: str | None = None
    metadata: tuple[tuple[str, MetadataValue], ...] = ()
    projection_policy: str | None = None
    projection_behavior: ProjectionBehavior = ProjectionBehavior.PUBLIC_SAFE
    public_alias: str | None = None
    redaction_label: str | None = None
    private_binding_refs: tuple[str, ...] = ()
    local_overlay_refs: tuple[str, ...] = ()
    source: Source = Source.PLATFORM
    local_path: str | None = None
    local_port: int | None = None
    env_file: str | None = None
    endpoint_override: str | None = None
    cache_path: str | None = None
    gpu_required: bool | None = None
    runtime_hints: tuple[tuple[str, "str | int | float | bool"], ...] = ()


@dataclass(frozen=True)
class RepoEdge:
    src: str
    dst: str
    type: RepoEdgeType
    source: Source = Source.PLATFORM


@dataclass(frozen=True)
class OntologyRelationship:
    relationship_id: str
    source_id: str
    target_id: str
    kind: OntologyRelationshipKind
    visibility: Visibility = Visibility.PUBLIC
    projection_behavior: ProjectionBehavior = ProjectionBehavior.PUBLIC_SAFE
    policy_ref: str | None = None
    redaction_label: str | None = None
    metadata: tuple[tuple[str, MetadataValue], ...] = ()
    source: Source = Source.PLATFORM


@dataclass(frozen=True)
class ManifestHeader:
    """Top-of-file metadata every manifest carries."""

    manifest_kind: ManifestKind
    manifest_version: str


@dataclass(frozen=True)
class PrivateManifest:
    """Typed wrapper for a first-class private platform superset manifest."""

    header: ManifestHeader
    graph: "RepoGraph"


@dataclass
class RepoGraph:
    """Parsed nodes, edges, and ontology relationships."""

    nodes: dict[str, RepoNode] = field(default_factory=dict)
    edges: tuple[RepoEdge, ...] = ()
    relationships: tuple[OntologyRelationship, ...] = ()
    _name_index: dict[str, str] = field(default_factory=dict, repr=False)

    @classmethod
    def build(
        cls,
        nodes: list[RepoNode],
        edges: list[RepoEdge],
        relationships: list[OntologyRelationship] | None = None,
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
        rel_map: dict[str, OntologyRelationship] = {}
        for relationship in relationships or []:
            if relationship.relationship_id in rel_map:
                raise RepoGraphConfigError(
                    f"duplicate relationship id: {relationship.relationship_id}"
                )
            if relationship.source_id not in node_map:
                raise RepoGraphConfigError(
                    f"relationship {relationship.relationship_id} references "
                    f"unknown source '{relationship.source_id}'"
                )
            if relationship.target_id not in node_map:
                raise RepoGraphConfigError(
                    f"relationship {relationship.relationship_id} references "
                    f"unknown target '{relationship.target_id}'"
                )
            rel_map[relationship.relationship_id] = relationship
        return cls(
            nodes=node_map,
            edges=tuple(edges),
            relationships=tuple(rel_map.values()),
            _name_index=name_index,
        )

    def list_nodes(self) -> list[RepoNode]:
        return sorted(self.nodes.values(), key=lambda n: n.canonical_name)

    def resolve(self, name: str) -> RepoNode | None:
        repo_id = self._name_index.get(name.lower())
        if repo_id is None:
            return None
        return self.nodes[repo_id]

    def upstream(self, repo_id: str) -> list[RepoNode]:
        if repo_id not in self.nodes:
            raise KeyError(repo_id)
        targets = {e.dst for e in self.edges if e.src == repo_id}
        return [self.nodes[t] for t in sorted(targets)]

    def downstream(self, repo_id: str) -> list[RepoNode]:
        if repo_id not in self.nodes:
            raise KeyError(repo_id)
        sources = {e.src for e in self.edges if e.dst == repo_id}
        return [self.nodes[s] for s in sorted(sources)]

    def affected_by_contract_change(self, repo_id: str) -> list[RepoNode]:
        if repo_id not in self.nodes:
            raise KeyError(repo_id)
        consumers = {
            e.src
            for e in self.edges
            if e.dst == repo_id and e.type == RepoEdgeType.DEPENDS_ON_CONTRACTS_FROM
        }
        return [self.nodes[c] for c in sorted(consumers)]

    def who_consumes_assets_of(self, repo_id: str) -> list[RepoNode]:
        if repo_id not in self.nodes:
            raise KeyError(repo_id)
        consumers = {
            e.src
            for e in self.edges
            if e.dst == repo_id and e.type == RepoEdgeType.BUNDLES_ASSETS_FROM
        }
        return [self.nodes[c] for c in sorted(consumers)]

    def who_dispatches_to(self, repo_id: str) -> list[RepoNode]:
        if repo_id not in self.nodes:
            raise KeyError(repo_id)
        dispatchers = {
            e.src
            for e in self.edges
            if e.dst == repo_id and e.type == RepoEdgeType.DISPATCHES_TO
        }
        return [self.nodes[d] for d in sorted(dispatchers)]

    def list_relationships(self) -> list[OntologyRelationship]:
        return sorted(self.relationships, key=lambda r: r.relationship_id)

    def relationships_by_kind(
        self,
        kind: OntologyRelationshipKind,
    ) -> list[OntologyRelationship]:
        return [r for r in self.list_relationships() if r.kind is kind]

    def relationships_from(
        self,
        source_id: str,
        *,
        visibility: Visibility | None = None,
        projection_behavior: ProjectionBehavior | None = None,
    ) -> list[OntologyRelationship]:
        return [
            r
            for r in self.list_relationships()
            if r.source_id == source_id
            and (visibility is None or r.visibility is visibility)
            and (
                projection_behavior is None
                or r.projection_behavior is projection_behavior
            )
        ]

    def relationships_to(
        self,
        target_id: str,
        *,
        visibility: Visibility | None = None,
        projection_behavior: ProjectionBehavior | None = None,
    ) -> list[OntologyRelationship]:
        return [
            r
            for r in self.list_relationships()
            if r.target_id == target_id
            and (visibility is None or r.visibility is visibility)
            and (
                projection_behavior is None
                or r.projection_behavior is projection_behavior
            )
        ]


EffectiveRepoGraph = RepoGraph
