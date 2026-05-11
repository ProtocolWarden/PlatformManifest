# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 ProtocolWarden
"""YAML loader for PlatformManifest graphs."""

from __future__ import annotations

from importlib import resources
from pathlib import Path
from typing import Any

import yaml

from .models import (
    LOCAL_ANNOTATION_FIELDS,
    EntityKind,
    ManifestKind,
    OntologyRelationship,
    OntologyRelationshipKind,
    ProjectionBehavior,
    RepoEdge,
    RepoEdgeType,
    RepoGraph,
    RepoGraphConfigError,
    RepoNode,
    Source,
    Visibility,
    default_projection_behavior_for_visibility,
)


_PLATFORM_MANIFEST_FILENAME = "platform_manifest.yaml"


def default_config_path() -> Path:
    return Path(str(
        resources.files("platform_manifest") / "data" / _PLATFORM_MANIFEST_FILENAME
    ))


_cached_default: RepoGraph | None = None


def load_default_repo_graph() -> RepoGraph:
    global _cached_default
    if _cached_default is None:
        _cached_default = load_repo_graph(default_config_path())
    return _cached_default


def load_repo_graph(
    path: Path,
    *,
    expected_kind: ManifestKind = ManifestKind.PLATFORM,
) -> RepoGraph:
    """Load a platform/private/project manifest and return its RepoGraph."""
    if expected_kind is ManifestKind.LOCAL:
        raise RepoGraphConfigError(
            "load_repo_graph does not load LocalManifest files; "
            "use composition.load_local_layer or load_effective_graph"
        )
    if expected_kind is ManifestKind.WORK_SCOPE:
        raise RepoGraphConfigError(
            "load_repo_graph does not load WorkScopeManifest files standalone; "
            "use load_effective_graph(base, work_scope=...)"
        )

    raw = _read_manifest(path)
    _validate_header(raw, expected_kind=expected_kind, path=path)

    repos_raw = raw.get("repos") or {}
    edges_raw = raw.get("edges") or []
    relationships_raw = raw.get("relationships") or []
    if not isinstance(repos_raw, dict):
        raise RepoGraphConfigError("'repos' must be a mapping of repo_id -> fields")
    if not isinstance(edges_raw, list):
        raise RepoGraphConfigError("'edges' must be a list of {from,to,type} mappings")
    if not isinstance(relationships_raw, list):
        raise RepoGraphConfigError(
            "'relationships' must be a list of {id,source,target,kind} mappings"
        )

    source = _source_for_manifest_kind(expected_kind)
    nodes = [_parse_node(repo_id, fields, source=source) for repo_id, fields in repos_raw.items()]

    if expected_kind is ManifestKind.PLATFORM:
        _enforce_platform_public_only(nodes)

    name_to_id: dict[str, str] = {}
    for node in nodes:
        name_to_id[node.canonical_name.lower()] = node.repo_id
        name_to_id[node.repo_id.lower()] = node.repo_id
        if node.public_alias:
            name_to_id[node.public_alias.lower()] = node.repo_id

    edges = _parse_edges(edges_raw, name_to_id=name_to_id, source=source)
    relationships = _parse_relationships(
        relationships_raw,
        name_to_id=name_to_id,
        source=source,
    )

    return RepoGraph.build(nodes=nodes, edges=edges, relationships=relationships)


def read_manifest_raw(path: Path) -> dict[str, Any]:
    return _read_manifest(path)


def validate_header(
    raw: dict[str, Any],
    *,
    expected_kind: ManifestKind,
    path: Path,
) -> None:
    _validate_header(raw, expected_kind=expected_kind, path=path)


def parse_nodes(raw: dict[str, Any], *, source: Source) -> list[RepoNode]:
    repos_raw = raw.get("repos") or {}
    if not isinstance(repos_raw, dict):
        raise RepoGraphConfigError("'repos' must be a mapping of repo_id -> fields")
    return [_parse_node(repo_id, fields, source=source) for repo_id, fields in repos_raw.items()]


def parse_edges(
    raw: dict[str, Any],
    *,
    name_to_id: dict[str, str],
    source: Source,
) -> list[RepoEdge]:
    edges_raw = raw.get("edges") or []
    if not isinstance(edges_raw, list):
        raise RepoGraphConfigError("'edges' must be a list of {from,to,type} mappings")
    return _parse_edges(edges_raw, name_to_id=name_to_id, source=source)


def parse_relationships(
    raw: dict[str, Any],
    *,
    name_to_id: dict[str, str],
    source: Source,
) -> list[OntologyRelationship]:
    relationships_raw = raw.get("relationships") or []
    if not isinstance(relationships_raw, list):
        raise RepoGraphConfigError(
            "'relationships' must be a list of {id,source,target,kind} mappings"
        )
    return _parse_relationships(relationships_raw, name_to_id=name_to_id, source=source)


def _read_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise RepoGraphConfigError(f"manifest not found: {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise RepoGraphConfigError(f"manifest root must be a mapping: {path}")
    return raw


def _validate_header(
    raw: dict[str, Any],
    *,
    expected_kind: ManifestKind,
    path: Path,
) -> None:
    kind_raw = raw.get("manifest_kind")
    if kind_raw is None:
        raise RepoGraphConfigError(
            f"manifest at {path} missing required field 'manifest_kind' "
            f"(expected '{expected_kind.value}')"
        )
    try:
        kind = ManifestKind(kind_raw)
    except ValueError as exc:
        raise RepoGraphConfigError(
            f"manifest at {path} has unknown manifest_kind={kind_raw!r}; "
            f"allowed: {[k.value for k in ManifestKind]}"
        ) from exc
    if kind is not expected_kind:
        raise RepoGraphConfigError(
            f"expected manifest_kind={expected_kind.value!r} for this slot; "
            f"got manifest_kind={kind.value!r} at {path}"
        )

    version_raw = raw.get("manifest_version")
    if not version_raw or not isinstance(version_raw, str):
        raise RepoGraphConfigError(
            f"manifest at {path} missing required string field 'manifest_version'"
        )


def _source_for_manifest_kind(kind: ManifestKind) -> Source:
    if kind is ManifestKind.PLATFORM:
        return Source.PLATFORM
    if kind is ManifestKind.PRIVATE:
        return Source.PRIVATE
    if kind is ManifestKind.PROJECT:
        return Source.PROJECT
    if kind is ManifestKind.WORK_SCOPE:
        return Source.WORK_SCOPE
    raise RepoGraphConfigError(f"manifest kind {kind.value!r} does not create graph nodes")


def _parse_node(
    repo_id: object,
    fields: object,
    *,
    source: Source,
) -> RepoNode:
    if not isinstance(fields, dict):
        raise RepoGraphConfigError(f"repo '{repo_id}' fields must be a mapping")

    leaked = LOCAL_ANNOTATION_FIELDS & set(fields.keys())
    if leaked:
        raise RepoGraphConfigError(
            f"repo '{repo_id}' has local-only field(s) {sorted(leaked)} "
            f"in a {source.value} manifest; local annotations belong in a LocalManifest"
        )

    canonical = fields.get("canonical_name")
    if not canonical or not isinstance(canonical, str):
        raise RepoGraphConfigError(f"repo '{repo_id}' missing canonical_name")
    legacy = _parse_string_list(repo_id, fields, "legacy_names")
    visibility = _parse_visibility(repo_id, fields)
    return RepoNode(
        repo_id=str(repo_id),
        canonical_name=canonical,
        visibility=visibility,
        legacy_names=legacy,
        github_url=_opt_str(fields, "github_url"),
        runtime_role=_opt_str(fields, "runtime_role"),
        kind=_parse_kind(repo_id, fields),
        owner=_opt_str(fields, "owner"),
        scope=_opt_str(fields, "scope"),
        metadata=_parse_metadata(repo_id, fields),
        projection_policy=_opt_str(fields, "projection_policy"),
        projection_behavior=_parse_projection_behavior(repo_id, fields, visibility=visibility),
        public_alias=_opt_str(fields, "public_alias"),
        redaction_label=_opt_str(fields, "redaction_label"),
        private_binding_refs=_parse_string_list(repo_id, fields, "private_binding_refs"),
        local_overlay_refs=_parse_string_list(repo_id, fields, "local_overlay_refs"),
        source=source,
    )


def _parse_visibility(repo_id: object, fields: dict[str, Any]) -> Visibility:
    raw = fields.get("visibility")
    if raw is None:
        raise RepoGraphConfigError(
            f"repo '{repo_id}' missing required 'visibility' field "
            f"(allowed: {[v.value for v in Visibility]})"
        )
    try:
        return Visibility(raw)
    except ValueError as exc:
        raise RepoGraphConfigError(
            f"repo '{repo_id}' has unknown visibility={raw!r}; "
            f"allowed: {[v.value for v in Visibility]}"
        ) from exc


def _parse_projection_behavior(
    repo_id: object,
    fields: dict[str, Any],
    *,
    visibility: Visibility,
) -> ProjectionBehavior:
    raw = fields.get("projection_behavior")
    if raw is None:
        return default_projection_behavior_for_visibility(visibility)
    try:
        return ProjectionBehavior(raw)
    except ValueError as exc:
        raise RepoGraphConfigError(
            f"repo '{repo_id}' has unknown projection_behavior={raw!r}; "
            f"allowed: {[b.value for b in ProjectionBehavior]}"
        ) from exc


def _parse_kind(repo_id: object, fields: dict[str, Any]) -> EntityKind:
    raw = fields.get("kind", EntityKind.REPOSITORY.value)
    try:
        return EntityKind(raw)
    except ValueError as exc:
        raise RepoGraphConfigError(
            f"repo '{repo_id}' has unknown kind={raw!r}; "
            f"allowed: {[k.value for k in EntityKind]}"
        ) from exc


def _enforce_platform_public_only(nodes: list[RepoNode]) -> None:
    private = [n.repo_id for n in nodes if n.visibility is not Visibility.PUBLIC]
    if private:
        raise RepoGraphConfigError(
            f"PlatformManifest may only contain public nodes; "
            f"non-public node(s): {private}"
        )


def _parse_edges(
    edges_raw: list[Any],
    *,
    name_to_id: dict[str, str],
    source: Source,
) -> list[RepoEdge]:
    edges: list[RepoEdge] = []
    for idx, item in enumerate(edges_raw):
        if not isinstance(item, dict):
            raise RepoGraphConfigError(f"edge #{idx} must be a mapping")
        src_name = item.get("from")
        dst_name = item.get("to")
        edge_type_raw = item.get("type")
        if not (src_name and dst_name and edge_type_raw):
            raise RepoGraphConfigError(f"edge #{idx} requires 'from', 'to', and 'type'")
        try:
            edge_type = RepoEdgeType(edge_type_raw)
        except ValueError as exc:
            raise RepoGraphConfigError(
                f"edge #{idx} has unknown type '{edge_type_raw}'; "
                f"allowed: {[t.value for t in RepoEdgeType]}"
            ) from exc
        src_id = _resolve_name(name_to_id, str(src_name), f"edge #{idx} 'from'")
        dst_id = _resolve_name(name_to_id, str(dst_name), f"edge #{idx} 'to'")
        edges.append(RepoEdge(src=src_id, dst=dst_id, type=edge_type, source=source))
    return edges


def _parse_relationships(
    relationships_raw: list[Any],
    *,
    name_to_id: dict[str, str],
    source: Source,
) -> list[OntologyRelationship]:
    relationships: list[OntologyRelationship] = []
    for idx, item in enumerate(relationships_raw):
        if not isinstance(item, dict):
            raise RepoGraphConfigError(f"relationship #{idx} must be a mapping")
        rel_id_raw = item.get("id") or f"{source.value}-relationship-{idx}"
        source_name = item.get("source")
        target_name = item.get("target")
        kind_raw = item.get("kind")
        if not (source_name and target_name and kind_raw):
            raise RepoGraphConfigError(
                f"relationship #{idx} requires 'source', 'target', and 'kind'"
            )
        try:
            kind = OntologyRelationshipKind(kind_raw)
        except ValueError as exc:
            raise RepoGraphConfigError(
                f"relationship #{idx} has unknown kind '{kind_raw}'; "
                f"allowed: {[k.value for k in OntologyRelationshipKind]}"
            ) from exc
        visibility = _parse_relationship_visibility(item, idx)
        projection_behavior = _parse_relationship_projection_behavior(
            item, idx, visibility=visibility
        )
        relationships.append(
            OntologyRelationship(
                relationship_id=str(rel_id_raw),
                source_id=_resolve_name(name_to_id, str(source_name), f"relationship #{idx} 'source'"),
                target_id=_resolve_name(name_to_id, str(target_name), f"relationship #{idx} 'target'"),
                kind=kind,
                visibility=visibility,
                projection_behavior=projection_behavior,
                policy_ref=_opt_str(item, "policy_ref"),
                redaction_label=_opt_str(item, "redaction_label"),
                metadata=_parse_metadata(f"relationship #{idx}", item),
                source=source,
            )
        )
    return relationships


def _parse_relationship_visibility(
    item: dict[str, Any],
    idx: int,
) -> Visibility:
    raw = item.get("visibility")
    if raw is None:
        raise RepoGraphConfigError(
            f"relationship #{idx} missing required 'visibility' field "
            f"(allowed: {[v.value for v in Visibility]})"
        )
    try:
        return Visibility(raw)
    except ValueError as exc:
        raise RepoGraphConfigError(
            f"relationship #{idx} has unknown visibility={raw!r}; "
            f"allowed: {[v.value for v in Visibility]}"
        ) from exc


def _parse_relationship_projection_behavior(
    item: dict[str, Any],
    idx: int,
    *,
    visibility: Visibility,
) -> ProjectionBehavior:
    raw = item.get("projection_behavior")
    if raw is None:
        raise RepoGraphConfigError(
            f"relationship #{idx} missing required 'projection_behavior' field "
            f"(allowed: {[b.value for b in ProjectionBehavior]})"
        )
    try:
        return ProjectionBehavior(raw)
    except ValueError as exc:
        raise RepoGraphConfigError(
            f"relationship #{idx} has unknown projection_behavior={raw!r}; "
            f"allowed: {[b.value for b in ProjectionBehavior]}"
        ) from exc


def _resolve_name(name_to_id: dict[str, str], raw: str, label: str) -> str:
    resolved = name_to_id.get(raw.lower())
    if resolved is None:
        raise RepoGraphConfigError(f"{label} unknown: {raw}")
    return resolved


def _opt_str(fields: dict[str, Any], key: str) -> str | None:
    val = fields.get(key)
    if val is None:
        return None
    if not isinstance(val, str):
        raise RepoGraphConfigError(f"field '{key}' must be a string if present")
    return val


def _parse_string_list(
    owner: object,
    fields: dict[str, Any],
    key: str,
) -> tuple[str, ...]:
    raw = fields.get(key)
    if raw is None:
        return ()
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        raise RepoGraphConfigError(
            f"{owner!r} field '{key}' must be a list of strings"
        )
    return tuple(raw)


def _parse_metadata(
    owner: object,
    fields: dict[str, Any],
) -> tuple[tuple[str, str | int | float | bool], ...]:
    raw = fields.get("metadata")
    if raw is None:
        return ()
    if not isinstance(raw, dict):
        raise RepoGraphConfigError(f"{owner!r} metadata must be a mapping")
    normalized: list[tuple[str, str | int | float | bool]] = []
    for key, value in raw.items():
        if not isinstance(key, str):
            raise RepoGraphConfigError(f"{owner!r} metadata keys must be strings")
        if not isinstance(value, (str, int, float, bool)) or isinstance(value, bytes):
            raise RepoGraphConfigError(
                f"{owner!r} metadata[{key}] must be str/int/float/bool"
            )
        normalized.append((key, value))
    return tuple(sorted(normalized))
