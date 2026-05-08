# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Velascat
"""Manifest composition — PlatformManifest + ProjectManifest + LocalManifest.

Public entry point:
    load_effective_graph(base, *, project=None, local=None) -> RepoGraph

Order is platform → project → local. Each layer sees the result of the
previous one. Merge rules (per the design doc):

- Platform: public nodes only, no local-only fields
- Project: may add private/public nodes and edges, but cannot redefine
  platform repo_ids and cannot add platform-to-platform edges. Optional
  ``platform_manifest`` block can pin a PEP 440 version_constraint.
- Local: may only annotate existing nodes with allowlisted local fields
  (local_path/local_port/env_file/endpoint_override/cache_path/
  gpu_required/runtime_hints). It does not add nodes or edges.

Edges with the same (from, to, type) are deduped (later layers win the
provenance tag). Unknown edge types are configuration errors at parse
time.
"""

from __future__ import annotations

from dataclasses import replace
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

from .loader import (
    load_repo_graph,
    parse_edges,
    parse_nodes,
    read_manifest_raw,
    validate_header,
)
# load_repo_graph is the platform entry point used in load_effective_graph.
from .models import (
    LOCAL_ANNOTATION_FIELDS,
    ManifestKind,
    RepoEdge,
    RepoGraph,
    RepoGraphConfigError,
    RepoNode,
    Source,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_effective_graph(
    base: Path,
    *,
    project: Path | None = None,
    local: Path | None = None,
) -> RepoGraph:
    """Compose PlatformManifest + ProjectManifest + LocalManifest into the
    runtime graph consumed by OperationsCenter and friends.

    ``base`` is the platform manifest path. ``project`` and ``local`` are
    both optional. ``local`` may be passed without ``project`` if a
    deployment only annotates platform repos.

    Returns a ``RepoGraph`` whose nodes carry ``source`` provenance and,
    where applicable, populated local annotation fields.
    """
    platform_graph = load_repo_graph(base, expected_kind=ManifestKind.PLATFORM)
    nodes: dict[str, RepoNode] = dict(platform_graph.nodes)
    edges: list[RepoEdge] = list(platform_graph.edges)

    if project is not None:
        nodes, edges = _apply_project(project, nodes, edges)

    if local is not None:
        nodes = _apply_local(local, nodes)

    return RepoGraph.build(
        nodes=list(nodes.values()),
        edges=_dedupe_edges(edges),
    )


# ---------------------------------------------------------------------------
# Project layer
# ---------------------------------------------------------------------------


def _apply_project(
    path: Path,
    base_nodes: dict[str, RepoNode],
    base_edges: list[RepoEdge],
) -> tuple[dict[str, RepoNode], list[RepoEdge]]:
    raw = read_manifest_raw(path)
    validate_header(raw, expected_kind=ManifestKind.PROJECT, path=path)
    _validate_platform_pin(raw)

    # Parse project nodes first; these are the ones the project introduces.
    project_nodes = parse_nodes(raw, source=Source.PROJECT)

    # Rule 2 — collisions on repo_id are configuration errors.
    project_repo_ids = {n.repo_id for n in project_nodes}
    collisions = project_repo_ids & set(base_nodes.keys())
    if collisions:
        raise RepoGraphConfigError(
            f"ProjectManifest cannot redefine platform repo_id(s): {sorted(collisions)}"
        )

    # Build a union name-index so project edges can reference both
    # project nodes and platform nodes (the common case).
    union_name_to_id: dict[str, str] = {}
    for node in (*base_nodes.values(), *project_nodes):
        union_name_to_id[node.canonical_name.lower()] = node.repo_id
        union_name_to_id[node.repo_id.lower()] = node.repo_id
        for alias in node.legacy_names:
            union_name_to_id[alias.lower()] = node.repo_id

    project_edges = parse_edges(raw, name_to_id=union_name_to_id, source=Source.PROJECT)

    # Rule 2 — project edges may not be platform→platform. Platform edges
    # are exactly those whose endpoints are both already in base_nodes.
    for edge in project_edges:
        if edge.src in base_nodes and edge.dst in base_nodes:
            raise RepoGraphConfigError(
                f"ProjectManifest cannot add platform-to-platform edge "
                f"{edge.src} -> {edge.dst} ({edge.type.value})"
            )

    merged_nodes = dict(base_nodes)
    for node in project_nodes:
        merged_nodes[node.repo_id] = node

    return merged_nodes, list(base_edges) + list(project_edges)


def _validate_platform_pin(raw: dict[str, Any]) -> None:
    """If the project pins a platform_manifest version_constraint, verify it
    against the installed ``platform-manifest`` distribution."""
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
        # Tests sometimes run before install; if we can't find the
        # distribution, skip the check rather than fail spuriously.
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


# ---------------------------------------------------------------------------
# Local layer
# ---------------------------------------------------------------------------


def _apply_local(
    path: Path,
    nodes: dict[str, RepoNode],
) -> dict[str, RepoNode]:
    raw = read_manifest_raw(path)
    validate_header(raw, expected_kind=ManifestKind.LOCAL, path=path)

    repos_raw = raw.get("repos") or {}
    if not isinstance(repos_raw, dict):
        raise RepoGraphConfigError(
            f"LocalManifest at {path}: 'repos' must be a mapping"
        )

    annotated = dict(nodes)
    for repo_id, fields in repos_raw.items():
        if not isinstance(fields, dict):
            raise RepoGraphConfigError(
                f"LocalManifest repo '{repo_id}' fields must be a mapping"
            )
        if repo_id not in annotated:
            raise RepoGraphConfigError(
                f"LocalManifest references unknown repo_id '{repo_id}'; "
                f"local annotations may only attach to platform or project repos"
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
        raise RepoGraphConfigError(
            f"LocalManifest '{key}' must be a non-empty string"
        )
    return val


# ---------------------------------------------------------------------------
# Edge dedup
# ---------------------------------------------------------------------------


def _dedupe_edges(edges: list[RepoEdge]) -> list[RepoEdge]:
    """Drop duplicates of (src, dst, type). First occurrence wins —
    platform edges out-rank project edges with the same shape, which
    matches the layering order. Different edge types between the same
    pair are kept."""
    seen: set[tuple[str, str, str]] = set()
    out: list[RepoEdge] = []
    for edge in edges:
        key = (edge.src, edge.dst, edge.type.value)
        if key in seen:
            continue
        seen.add(key)
        out.append(edge)
    return out


__all__ = ["load_effective_graph"]
