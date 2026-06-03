# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 ProtocolWarden
"""Manifest composition for platform, private, project, work-scope, and local layers."""

from __future__ import annotations

from dataclasses import replace
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

from .errors import RepoGraphConfigError
from .loader import (
    load_repo_graph,
    parse_edges,
    parse_nodes,
    parse_relationships,
    read_manifest_raw,
    validate_header,
)
from .models import (
    LOCAL_ANNOTATION_FIELDS,
    ManifestKind,
    OntologyRelationship,
    RepoEdge,
    RepoGraph,
    RepoNode,
    Source,
)


_DEFAULT_INCLUDE_DEPTH = 4


def load_effective_graph(
    base: Path,
    *,
    private: Path | None = None,
    project: Path | None = None,
    work_scope: Path | None = None,
    local: Path | None = None,
    max_include_depth: int = _DEFAULT_INCLUDE_DEPTH,
) -> RepoGraph:
    """Compose platform -> private -> (project xor work_scope) -> local."""
    if project is not None and work_scope is not None:
        raise RepoGraphConfigError(
            "load_effective_graph: 'project' and 'work_scope' are mutually "
            "exclusive — use exactly one of ProjectManifest or "
            "WorkScopeManifest as the second composition layer"
        )

    platform_graph = load_repo_graph(base, expected_kind=ManifestKind.PLATFORM)
    nodes: dict[str, RepoNode] = dict(platform_graph.nodes)
    edges: list[RepoEdge] = list(platform_graph.edges)
    relationships: list[OntologyRelationship] = list(platform_graph.relationships)
    platform_node_ids: frozenset[str] = frozenset(nodes.keys())

    if private is not None:
        nodes, edges, relationships = _apply_layer(
            private,
            expected_kind=ManifestKind.PRIVATE,
            node_source=Source.PRIVATE,
            accumulated_nodes=nodes,
            accumulated_edges=edges,
            accumulated_relationships=relationships,
            platform_node_ids=platform_node_ids,
        )

    if project is not None:
        nodes, edges, relationships = _apply_project(
            project,
            nodes,
            edges,
            relationships,
            platform_node_ids=platform_node_ids,
            max_depth=max_include_depth,
        )

    if work_scope is not None:
        nodes, edges, relationships = _apply_work_scope(
            work_scope,
            nodes,
            edges,
            relationships,
            platform_node_ids=platform_node_ids,
            max_depth=max_include_depth,
        )

    if local is not None:
        nodes = _apply_local(local, nodes)

    return RepoGraph.build(
        nodes=list(nodes.values()),
        edges=_dedupe_edges(edges),
        relationships=_dedupe_relationships(relationships),
    )


def _apply_layer(
    path: Path,
    *,
    expected_kind: ManifestKind,
    node_source: Source,
    accumulated_nodes: dict[str, RepoNode],
    accumulated_edges: list[RepoEdge],
    accumulated_relationships: list[OntologyRelationship],
    platform_node_ids: frozenset[str],
) -> tuple[dict[str, RepoNode], list[RepoEdge], list[OntologyRelationship]]:
    raw = read_manifest_raw(path)
    validate_header(raw, expected_kind=expected_kind, path=path)
    if expected_kind is not ManifestKind.PRIVATE:
        _validate_platform_pin(raw)

    layer_nodes = parse_nodes(raw, source=node_source)
    layer_repo_ids = {n.repo_id for n in layer_nodes}

    platform_collisions = layer_repo_ids & platform_node_ids
    if platform_collisions:
        raise RepoGraphConfigError(
            f"{expected_kind.value.title()}Manifest at {path} cannot redefine "
            f"platform repo_id(s): {sorted(platform_collisions)}"
        )
    sibling_collisions = layer_repo_ids & (set(accumulated_nodes.keys()) - platform_node_ids)
    if sibling_collisions:
        raise RepoGraphConfigError(
            f"{expected_kind.value.title()}Manifest at {path} cannot redefine repo_id(s) "
            f"{sorted(sibling_collisions)} already declared by an earlier layer"
        )

    union_name_to_id = _build_name_index((*accumulated_nodes.values(), *layer_nodes))
    layer_edges = parse_edges(raw, name_to_id=union_name_to_id, source=node_source)
    layer_relationships = parse_relationships(
        raw, name_to_id=union_name_to_id, source=node_source
    )

    for edge in layer_edges:
        if edge.src in platform_node_ids and edge.dst in platform_node_ids:
            raise RepoGraphConfigError(
                f"{expected_kind.value.title()}Manifest at {path} cannot add platform-to-platform "
                f"edge {edge.src} -> {edge.dst} ({edge.type.value})"
            )
    for relationship in layer_relationships:
        if (
            relationship.source_id in platform_node_ids
            and relationship.target_id in platform_node_ids
        ):
            raise RepoGraphConfigError(
                f"{expected_kind.value.title()}Manifest at {path} cannot add platform-to-platform "
                f"relationship {relationship.source_id} -> {relationship.target_id} "
                f"({relationship.kind.value})"
            )

    merged_nodes = dict(accumulated_nodes)
    for node in layer_nodes:
        merged_nodes[node.repo_id] = node

    return (
        merged_nodes,
        list(accumulated_edges) + list(layer_edges),
        list(accumulated_relationships) + list(layer_relationships),
    )


def _apply_includes(
    raw: dict[str, Any],
    parent_path: Path,
    accumulated_nodes: dict[str, RepoNode],
    accumulated_edges: list[RepoEdge],
    accumulated_relationships: list[OntologyRelationship],
    *,
    platform_node_ids: frozenset[str],
    max_depth: int,
    _visited: frozenset[Path],
    _depth: int,
) -> tuple[dict[str, RepoNode], list[RepoEdge], list[OntologyRelationship]]:
    includes = raw.get("includes") or []
    if not isinstance(includes, list):
        raise RepoGraphConfigError(f"ProjectManifest 'includes' must be a list at {parent_path}")
    for idx, inc in enumerate(includes):
        if not isinstance(inc, dict):
            raise RepoGraphConfigError(
                f"include #{idx} at {parent_path} must be a mapping with "
                f"{{name, project_manifest_path}}"
            )
        inc_path_raw = inc.get("project_manifest_path")
        if not inc_path_raw or not isinstance(inc_path_raw, str):
            raise RepoGraphConfigError(
                f"include #{idx} at {parent_path} missing required string "
                f"'project_manifest_path'"
            )
        inc_path = (parent_path.parent / Path(inc_path_raw)).resolve()
        accumulated_nodes, accumulated_edges, accumulated_relationships = _apply_project(
            inc_path,
            accumulated_nodes,
            accumulated_edges,
            accumulated_relationships,
            platform_node_ids=platform_node_ids,
            max_depth=max_depth,
            _visited=_visited,
            _depth=_depth,
        )
    return accumulated_nodes, accumulated_edges, accumulated_relationships


def _apply_project(
    path: Path,
    accumulated_nodes: dict[str, RepoNode],
    accumulated_edges: list[RepoEdge],
    accumulated_relationships: list[OntologyRelationship],
    *,
    platform_node_ids: frozenset[str],
    max_depth: int = _DEFAULT_INCLUDE_DEPTH,
    _visited: frozenset[Path] = frozenset(),
    _depth: int = 0,
) -> tuple[dict[str, RepoNode], list[RepoEdge], list[OntologyRelationship]]:
    if _depth > max_depth:
        chain = " -> ".join(str(p) for p in _visited) or "(root)"
        raise RepoGraphConfigError(
            f"ProjectManifest include depth exceeded {max_depth} at {path} "
            f"(chain: {chain})"
        )
    resolved = path.resolve()
    if resolved in _visited:
        chain = " -> ".join(str(p) for p in _visited)
        raise RepoGraphConfigError(
            f"ProjectManifest include cycle detected: {resolved} "
            f"already visited (chain: {chain})"
        )

    raw = read_manifest_raw(path)
    validate_header(raw, expected_kind=ManifestKind.PROJECT, path=path)
    _validate_platform_pin(raw)
    if raw.get("includes"):
        raise RepoGraphConfigError(
            f"ProjectManifest at {path} contains 'includes:' — multi-repo "
            f"composition is exclusively the role of WorkScopeManifest "
            f"(manifest_kind: work_scope) since PlatformManifest v1.0.0. "
            f"Migrate by changing 'manifest_kind: project' to "
            f"'manifest_kind: work_scope'; the includes shape is unchanged."
        )

    return _apply_layer(
        path,
        expected_kind=ManifestKind.PROJECT,
        node_source=Source.PROJECT,
        accumulated_nodes=accumulated_nodes,
        accumulated_edges=accumulated_edges,
        accumulated_relationships=accumulated_relationships,
        platform_node_ids=platform_node_ids,
    )


def _validate_platform_pin(raw: dict[str, Any]) -> None:
    pin = raw.get("platform_manifest")
    if pin is None:
        return
    if not isinstance(pin, dict):
        raise RepoGraphConfigError(
            "ProjectManifest 'platform_manifest' must be a mapping with "
            "{name, version_constraint}"
        )
    constraint = pin.get("version_constraint")
    if constraint is None:
        return
    if not isinstance(constraint, str) or not constraint.strip():
        raise RepoGraphConfigError(
            "ProjectManifest 'platform_manifest.version_constraint' must be a non-empty string"
        )
    try:
        spec = SpecifierSet(constraint)
    except InvalidSpecifier as exc:
        raise RepoGraphConfigError(
            f"ProjectManifest 'platform_manifest.version_constraint' is not a valid "
            f"PEP 440 specifier: {constraint!r}"
        ) from exc
    try:
        installed = importlib_metadata.version("platform-manifest")
    except importlib_metadata.PackageNotFoundError:
        return
    try:
        installed_v = Version(installed)
    except InvalidVersion as exc:
        raise RepoGraphConfigError(
            f"installed platform-manifest version {installed!r} is not PEP 440"
        ) from exc
    if installed_v not in spec:
        raise RepoGraphConfigError(
            f"installed platform-manifest {installed} does not satisfy "
            f"ProjectManifest constraint {constraint!r}"
        )


def _apply_work_scope(
    path: Path,
    accumulated_nodes: dict[str, RepoNode],
    accumulated_edges: list[RepoEdge],
    accumulated_relationships: list[OntologyRelationship],
    *,
    platform_node_ids: frozenset[str],
    max_depth: int = _DEFAULT_INCLUDE_DEPTH,
) -> tuple[dict[str, RepoNode], list[RepoEdge], list[OntologyRelationship]]:
    raw = read_manifest_raw(path)
    validate_header(raw, expected_kind=ManifestKind.WORK_SCOPE, path=path)
    _validate_platform_pin(raw)

    resolved = path.resolve()
    visited: frozenset[Path] = frozenset({resolved})

    accumulated_nodes, accumulated_edges, accumulated_relationships = _apply_includes(
        raw,
        path,
        accumulated_nodes,
        accumulated_edges,
        accumulated_relationships,
        platform_node_ids=platform_node_ids,
        max_depth=max_depth,
        _visited=visited,
        _depth=1,
    )

    return _apply_layer(
        path,
        expected_kind=ManifestKind.WORK_SCOPE,
        node_source=Source.WORK_SCOPE,
        accumulated_nodes=accumulated_nodes,
        accumulated_edges=accumulated_edges,
        accumulated_relationships=accumulated_relationships,
        platform_node_ids=platform_node_ids,
    )


def _apply_local(
    path: Path,
    nodes: dict[str, RepoNode],
) -> dict[str, RepoNode]:
    raw = read_manifest_raw(path)
    validate_header(raw, expected_kind=ManifestKind.LOCAL, path=path)

    repos_raw = raw.get("repos") or {}
    if not isinstance(repos_raw, dict):
        raise RepoGraphConfigError(f"LocalManifest at {path}: 'repos' must be a mapping")

    annotated = dict(nodes)
    for repo_id, fields in repos_raw.items():
        if not isinstance(fields, dict):
            raise RepoGraphConfigError(
                f"LocalManifest repo '{repo_id}' fields must be a mapping"
            )
        if repo_id not in annotated:
            raise RepoGraphConfigError(
                f"LocalManifest references unknown repo_id '{repo_id}'; "
                f"local annotations may only attach to platform, private, or project repos"
            )
        bad = set(fields.keys()) - LOCAL_ANNOTATION_FIELDS
        if bad:
            raise RepoGraphConfigError(
                f"LocalManifest field(s) {sorted(bad)} not allowed on '{repo_id}'; "
                f"allowed fields: {sorted(LOCAL_ANNOTATION_FIELDS)}"
            )
        annotated[repo_id] = _annotate(annotated[repo_id], fields)
    return annotated


def _annotate(node: RepoNode, fields: dict[str, Any]) -> RepoNode:
    updates: dict[str, Any] = {}
    if "local_path" in fields:
        updates["local_path"] = _expect_str(fields, "local_path")
    if "local_port" in fields:
        port = fields["local_port"]
        if not isinstance(port, int) or isinstance(port, bool) or not (1 <= port <= 65535):
            raise RepoGraphConfigError(
                f"LocalManifest 'local_port' on '{node.repo_id}' must be an int in 1..65535"
            )
        updates["local_port"] = port
    if "env_file" in fields:
        updates["env_file"] = _expect_str(fields, "env_file")
    if "endpoint_override" in fields:
        updates["endpoint_override"] = _expect_str(fields, "endpoint_override")
    if "cache_path" in fields:
        updates["cache_path"] = _expect_str(fields, "cache_path")
    if "gpu_required" in fields:
        if not isinstance(fields["gpu_required"], bool):
            raise RepoGraphConfigError(
                f"LocalManifest 'gpu_required' on '{node.repo_id}' must be bool"
            )
        updates["gpu_required"] = fields["gpu_required"]
    if "runtime_hints" in fields:
        hints = fields["runtime_hints"]
        if not isinstance(hints, dict):
            raise RepoGraphConfigError(
                f"LocalManifest 'runtime_hints' on '{node.repo_id}' must be a mapping"
            )
        normalized: list[tuple[str, str | int | float | bool]] = []
        for k, v in hints.items():
            if not isinstance(k, str):
                raise RepoGraphConfigError(
                    f"LocalManifest 'runtime_hints' on '{node.repo_id}' has non-string key {k!r}"
                )
            if not isinstance(v, (str, int, float, bool)) or isinstance(v, bytes):
                raise RepoGraphConfigError(
                    f"LocalManifest 'runtime_hints[{k}]' on '{node.repo_id}' must be str/int/float/bool"
                )
            normalized.append((k, v))
        updates["runtime_hints"] = tuple(normalized)
    return replace(node, **updates)


def _expect_str(fields: dict[str, Any], key: str) -> str:
    val = fields[key]
    if not isinstance(val, str) or not val:
        raise RepoGraphConfigError(f"LocalManifest '{key}' must be a non-empty string")
    return val


def _build_name_index(nodes: tuple[RepoNode, ...] | list[RepoNode]) -> dict[str, str]:
    out: dict[str, str] = {}
    for node in nodes:
        out[node.canonical_name.lower()] = node.repo_id
        out[node.repo_id.lower()] = node.repo_id
        if node.public_alias:
            out[node.public_alias.lower()] = node.repo_id
    return out


def _dedupe_edges(edges: list[RepoEdge]) -> list[RepoEdge]:
    seen: set[tuple[str, str, str]] = set()
    out: list[RepoEdge] = []
    for edge in edges:
        key = (edge.src, edge.dst, edge.type.value)
        if key in seen:
            continue
        seen.add(key)
        out.append(edge)
    return out


def _dedupe_relationships(
    relationships: list[OntologyRelationship],
) -> list[OntologyRelationship]:
    seen: set[str] = set()
    out: list[OntologyRelationship] = []
    for relationship in relationships:
        if relationship.relationship_id in seen:
            continue
        seen.add(relationship.relationship_id)
        out.append(relationship)
    return out


__all__ = ["load_effective_graph"]
