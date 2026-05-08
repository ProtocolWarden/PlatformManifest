# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Velascat
"""YAML loader for repo graph manifests.

The canonical platform manifest ships as package data under
``platform_manifest/data/platform_manifest.yaml`` and is resolved via
``importlib.resources`` so installed wheels work the same as
source checkouts.

A manifest file's top-of-file header declares its trust slot:

    manifest_kind: platform | project | local
    manifest_version: "1.0.0"

Single-manifest entry points (this module):
- ``load_repo_graph(path, expected_kind=PLATFORM)`` — load a platform
  manifest into a RepoGraph (existing v0.2 surface).

Multi-layer composition lives in ``composition.py``:
- ``load_effective_graph(base, *, project=None, local=None)``.
"""

from __future__ import annotations

from importlib import resources
from pathlib import Path
from typing import Any

import yaml

from .models import (
    LOCAL_ANNOTATION_FIELDS,
    ManifestKind,
    RepoEdge,
    RepoEdgeType,
    RepoGraph,
    RepoGraphConfigError,
    RepoNode,
    Source,
    Visibility,
)


_PLATFORM_MANIFEST_FILENAME = "platform_manifest.yaml"


def default_config_path() -> Path:
    """Path to the bundled ``data/platform_manifest.yaml``."""
    return Path(str(
        resources.files("platform_manifest") / "data" / _PLATFORM_MANIFEST_FILENAME
    ))


_cached_default: RepoGraph | None = None


def load_default_repo_graph() -> RepoGraph:
    """Load + cache the bundled platform manifest."""
    global _cached_default
    if _cached_default is None:
        _cached_default = load_repo_graph(default_config_path())
    return _cached_default


def load_repo_graph(
    path: Path,
    *,
    expected_kind: ManifestKind = ManifestKind.PLATFORM,
) -> RepoGraph:
    """Load a platform or project manifest and return its RepoGraph.

    For local manifests, use ``load_local_layer`` since they don't form a
    standalone graph (they only annotate existing nodes).

    Raises ``RepoGraphConfigError`` on malformed YAML, wrong slot,
    missing required fields, private nodes in a platform manifest, or
    local-only fields appearing outside a LocalManifest.
    """
    if expected_kind is ManifestKind.LOCAL:
        raise RepoGraphConfigError(
            "load_repo_graph does not load LocalManifest files; "
            "use composition.load_local_layer or load_effective_graph"
        )
    if expected_kind is ManifestKind.WORK_SCOPE:
        raise RepoGraphConfigError(
            "load_repo_graph does not load WorkScopeManifest files standalone; "
            "use load_effective_graph(base, work_scope=...) — work scopes "
            "compose ProjectManifests and aren't a standalone graph"
        )
    raw = _read_manifest(path)
    _validate_header(raw, expected_kind=expected_kind, path=path)

    repos_raw = raw.get("repos") or {}
    edges_raw = raw.get("edges") or []
    if not isinstance(repos_raw, dict):
        raise RepoGraphConfigError("'repos' must be a mapping of repo_id → fields")
    if not isinstance(edges_raw, list):
        raise RepoGraphConfigError("'edges' must be a list of {from,to,type} mappings")

    source = Source.PLATFORM if expected_kind is ManifestKind.PLATFORM else Source.PROJECT

    nodes: list[RepoNode] = []
    for repo_id, fields in repos_raw.items():
        nodes.append(_parse_node(repo_id, fields, source=source))

    if expected_kind is ManifestKind.PLATFORM:
        _enforce_platform_public_only(nodes)

    name_to_id: dict[str, str] = {}
    for node in nodes:
        name_to_id[node.canonical_name.lower()] = node.repo_id
        name_to_id[node.repo_id.lower()] = node.repo_id

    edges = _parse_edges(edges_raw, name_to_id=name_to_id, source=source)

    return RepoGraph.build(nodes=nodes, edges=edges)


# ---------------------------------------------------------------------------
# Public helpers also used by composition.py
# ---------------------------------------------------------------------------


def read_manifest_raw(path: Path) -> dict[str, Any]:
    """Read + parse YAML, returning the top-level mapping. Raises on malformed."""
    return _read_manifest(path)


def validate_header(
    raw: dict[str, Any],
    *,
    expected_kind: ManifestKind,
    path: Path,
) -> None:
    """Public validator used by composition.py for project + local layers."""
    _validate_header(raw, expected_kind=expected_kind, path=path)


def parse_nodes(raw: dict[str, Any], *, source: Source) -> list[RepoNode]:
    """Public node parser used by composition.py for the project layer."""
    repos_raw = raw.get("repos") or {}
    if not isinstance(repos_raw, dict):
        raise RepoGraphConfigError("'repos' must be a mapping of repo_id → fields")
    return [_parse_node(repo_id, fields, source=source) for repo_id, fields in repos_raw.items()]


def parse_edges(
    raw: dict[str, Any],
    *,
    name_to_id: dict[str, str],
    source: Source,
) -> list[RepoEdge]:
    """Public edge parser. Caller supplies a union name index so project
    edges can reference both project and platform names."""
    edges_raw = raw.get("edges") or []
    if not isinstance(edges_raw, list):
        raise RepoGraphConfigError("'edges' must be a list of {from,to,type} mappings")
    return _parse_edges(edges_raw, name_to_id=name_to_id, source=source)


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


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


def _parse_node(
    repo_id: object,
    fields: object,
    *,
    source: Source,
) -> RepoNode:
    if not isinstance(fields, dict):
        raise RepoGraphConfigError(f"repo '{repo_id}' fields must be a mapping")

    # Local-only fields cannot appear in PlatformManifest or ProjectManifest.
    leaked = LOCAL_ANNOTATION_FIELDS & set(fields.keys())
    if leaked:
        raise RepoGraphConfigError(
            f"repo '{repo_id}' has local-only field(s) {sorted(leaked)} "
            f"in a {source.value} manifest; local annotations belong in a LocalManifest"
        )

    canonical = fields.get("canonical_name")
    if not canonical or not isinstance(canonical, str):
        raise RepoGraphConfigError(f"repo '{repo_id}' missing canonical_name")
    legacy = fields.get("legacy_names") or []
    if not isinstance(legacy, list) or not all(isinstance(s, str) for s in legacy):
        raise RepoGraphConfigError(
            f"repo '{repo_id}' legacy_names must be a list of strings"
        )
    visibility = _parse_visibility(repo_id, fields)
    return RepoNode(
        repo_id=str(repo_id),
        canonical_name=canonical,
        visibility=visibility,
        legacy_names=tuple(legacy),
        github_url=_opt_str(fields, "github_url"),
        runtime_role=_opt_str(fields, "runtime_role"),
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


def _enforce_platform_public_only(nodes: list[RepoNode]) -> None:
    private = [n.repo_id for n in nodes if n.visibility is Visibility.PRIVATE]
    if private:
        raise RepoGraphConfigError(
            f"PlatformManifest may only contain public nodes; "
            f"private node(s): {private}"
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
            raise RepoGraphConfigError(
                f"edge #{idx} requires 'from', 'to', and 'type'"
            )
        try:
            edge_type = RepoEdgeType(edge_type_raw)
        except ValueError as exc:
            raise RepoGraphConfigError(
                f"edge #{idx} has unknown type '{edge_type_raw}'; "
                f"allowed: {[t.value for t in RepoEdgeType]}"
            ) from exc
        src_id = name_to_id.get(str(src_name).lower())
        dst_id = name_to_id.get(str(dst_name).lower())
        if src_id is None:
            raise RepoGraphConfigError(f"edge #{idx} 'from' unknown: {src_name}")
        if dst_id is None:
            raise RepoGraphConfigError(f"edge #{idx} 'to' unknown: {dst_name}")
        edges.append(RepoEdge(src=src_id, dst=dst_id, type=edge_type, source=source))
    return edges


def _opt_str(fields: dict[str, Any], key: str) -> str | None:
    val = fields.get(key)
    if val is None:
        return None
    if not isinstance(val, str):
        raise RepoGraphConfigError(f"field '{key}' must be a string if present")
    return val
