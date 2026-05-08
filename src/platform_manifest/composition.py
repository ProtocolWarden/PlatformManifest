# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Velascat
"""Manifest composition — PlatformManifest + ProjectManifest/WorkScopeManifest + LocalManifest.

Public entry point:
    load_effective_graph(base, *, project=None, work_scope=None, local=None) -> RepoGraph

Order is platform → (project XOR work_scope) → local. Each layer sees the
result of the previous one. Merge rules (per the design doc):

- Platform: public nodes only, no local-only fields.
- Project: describes one project. May add private/public nodes and edges,
  but cannot redefine platform repo_ids, cannot add platform-to-platform
  edges, and (since v1.0.0) must NOT include other manifests. Optional
  ``platform_manifest`` block can pin a PEP 440 version_constraint.
- WorkScope (v0.9.0+): composes multiple ProjectManifests via explicit
  ``includes:``. Same node/edge constraints as project, but its own
  declared nodes/edges carry Source.WORK_SCOPE provenance.
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


_DEFAULT_INCLUDE_DEPTH = 4


def load_effective_graph(
    base: Path,
    *,
    project: Path | None = None,
    work_scope: Path | None = None,
    local: Path | None = None,
    max_include_depth: int = _DEFAULT_INCLUDE_DEPTH,
) -> RepoGraph:
    """Compose PlatformManifest + (ProjectManifest XOR WorkScopeManifest) +
    LocalManifest into the runtime graph consumed by OperationsCenter.

    ``base`` is the platform manifest path. At most one of ``project`` and
    ``work_scope`` may be set:

    - ``project`` — one ProjectManifest describing a single project unit.
    - ``work_scope`` — one WorkScopeManifest composing multiple
      ProjectManifests via explicit ``includes:``. Added in v0.9.0.

    ``local`` is independent and may be passed alone (annotates platform
    repos only) or alongside either of the above.

    Since v1.0.0, ``project`` manifests must NOT carry ``includes:``;
    multi-repo composition is exclusively the role of ``work_scope``.

    Cycle detection is performed by visited-set; ``max_include_depth``
    bounds how deep recursion may go (default 4).

    Returns a ``RepoGraph`` whose nodes carry ``source`` provenance and,
    where applicable, populated local annotation fields.
    """
    if project is not None and work_scope is not None:
        raise RepoGraphConfigError(
            "load_effective_graph: 'project' and 'work_scope' are mutually "
            "exclusive — use exactly one of ProjectManifest or "
            "WorkScopeManifest as the second composition layer"
        )

    platform_graph = load_repo_graph(base, expected_kind=ManifestKind.PLATFORM)
    nodes: dict[str, RepoNode] = dict(platform_graph.nodes)
    edges: list[RepoEdge] = list(platform_graph.edges)
    platform_node_ids: frozenset[str] = frozenset(nodes.keys())

    if project is not None:
        nodes, edges = _apply_project(
            project,
            nodes,
            edges,
            platform_node_ids=platform_node_ids,
            max_depth=max_include_depth,
        )

    if work_scope is not None:
        nodes, edges = _apply_work_scope(
            work_scope,
            nodes,
            edges,
            platform_node_ids=platform_node_ids,
            max_depth=max_include_depth,
        )

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
    accumulated_nodes: dict[str, RepoNode],
    accumulated_edges: list[RepoEdge],
    *,
    platform_node_ids: frozenset[str],
    max_depth: int = _DEFAULT_INCLUDE_DEPTH,
    _visited: frozenset[Path] = frozenset(),
    _depth: int = 0,
) -> tuple[dict[str, RepoNode], list[RepoEdge]]:
    """Apply a project manifest's nodes + edges (recursively for includes).

    ``platform_node_ids`` is the immutable set of platform repo_ids —
    used by the platform-to-platform edge rule, which only treats true
    platform nodes (not sub-project nodes) as off-limits to project edges.

    ``_visited`` and ``_depth`` are recursion-control internals. Cycle
    detection raises ``RepoGraphConfigError`` if the same resolved path
    is encountered twice in the include chain.
    """
    if _depth > max_depth:
        chain = " → ".join(str(p) for p in _visited) or "(root)"
        raise RepoGraphConfigError(
            f"ProjectManifest include depth exceeded {max_depth} at {path} "
            f"(chain: {chain})"
        )
    resolved = path.resolve()
    if resolved in _visited:
        chain = " → ".join(str(p) for p in _visited)
        raise RepoGraphConfigError(
            f"ProjectManifest include cycle detected: {resolved} "
            f"already visited (chain: {chain})"
        )

    raw = read_manifest_raw(path)
    validate_header(raw, expected_kind=ManifestKind.PROJECT, path=path)
    _validate_platform_pin(raw)

    # v1.0.0: ProjectManifest must NOT include other manifests. The
    # schema rejects this at the JSON-Schema layer; this guard catches
    # the case where the schema was bypassed (direct loader call) so
    # the error message is the migration hint, not a generic 'unknown
    # field' complaint.
    if raw.get("includes"):
        raise RepoGraphConfigError(
            f"ProjectManifest at {path} contains 'includes:' — multi-repo "
            f"composition is exclusively the role of WorkScopeManifest "
            f"(manifest_kind: work_scope) since PlatformManifest v1.0.0. "
            f"Migrate by changing 'manifest_kind: project' to "
            f"'manifest_kind: work_scope'; the includes shape is unchanged."
        )

    # Parse this project's own nodes
    project_nodes = parse_nodes(raw, source=Source.PROJECT)
    project_repo_ids = {n.repo_id for n in project_nodes}

    # Rule 2 — collisions are configuration errors. Distinguish platform
    # collisions (the original v0.3 rule) from sibling-include collisions
    # (new in v0.8 — same rule, different actor).
    platform_collisions = project_repo_ids & platform_node_ids
    if platform_collisions:
        raise RepoGraphConfigError(
            f"ProjectManifest at {path} cannot redefine platform repo_id(s): "
            f"{sorted(platform_collisions)}"
        )
    sibling_collisions = project_repo_ids & (
        set(accumulated_nodes.keys()) - platform_node_ids
    )
    if sibling_collisions:
        raise RepoGraphConfigError(
            f"ProjectManifest at {path} cannot redefine repo_id(s) "
            f"{sorted(sibling_collisions)} already declared by an included "
            f"sub-project"
        )

    # Union name-index so project edges can reference platform nodes,
    # sibling sub-project nodes, AND this project's own nodes.
    union_name_to_id: dict[str, str] = {}
    for node in (*accumulated_nodes.values(), *project_nodes):
        union_name_to_id[node.canonical_name.lower()] = node.repo_id
        union_name_to_id[node.repo_id.lower()] = node.repo_id
        for alias in node.legacy_names:
            union_name_to_id[alias.lower()] = node.repo_id

    project_edges = parse_edges(raw, name_to_id=union_name_to_id, source=Source.PROJECT)

    # Rule 2 — project edges may not be platform→platform. Sub-project
    # edges to/from each other ARE allowed (they're the whole point of
    # the suite-include pattern).
    for edge in project_edges:
        if edge.src in platform_node_ids and edge.dst in platform_node_ids:
            raise RepoGraphConfigError(
                f"ProjectManifest at {path} cannot add platform-to-platform "
                f"edge {edge.src} -> {edge.dst} ({edge.type.value})"
            )

    merged_nodes = dict(accumulated_nodes)
    for node in project_nodes:
        merged_nodes[node.repo_id] = node

    return merged_nodes, list(accumulated_edges) + list(project_edges)


def _apply_includes(
    raw: dict[str, Any],
    parent_path: Path,
    accumulated_nodes: dict[str, RepoNode],
    accumulated_edges: list[RepoEdge],
    *,
    platform_node_ids: frozenset[str],
    max_depth: int,
    _visited: frozenset[Path],
    _depth: int,
) -> tuple[dict[str, RepoNode], list[RepoEdge]]:
    """Recursively apply a project's includes (sub-project manifests)."""
    includes = raw.get("includes") or []
    if not isinstance(includes, list):
        raise RepoGraphConfigError(
            f"ProjectManifest 'includes' must be a list at {parent_path}"
        )
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
        # Resolve relative to the including manifest's directory
        inc_path = (parent_path.parent / Path(inc_path_raw)).resolve()
        accumulated_nodes, accumulated_edges = _apply_project(
            inc_path,
            accumulated_nodes,
            accumulated_edges,
            platform_node_ids=platform_node_ids,
            max_depth=max_depth,
            _visited=_visited,
            _depth=_depth,
        )
    return accumulated_nodes, accumulated_edges


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
# Work-scope layer (v0.9.0+)
# ---------------------------------------------------------------------------


def _apply_work_scope(
    path: Path,
    accumulated_nodes: dict[str, RepoNode],
    accumulated_edges: list[RepoEdge],
    *,
    platform_node_ids: frozenset[str],
    max_depth: int = _DEFAULT_INCLUDE_DEPTH,
) -> tuple[dict[str, RepoNode], list[RepoEdge]]:
    """Apply a WorkScopeManifest's includes + own nodes/edges.

    A WorkScopeManifest is the explicit multi-project composition layer.
    Its ``includes:`` reference ProjectManifests (one per included project),
    which contribute Source.PROJECT nodes/edges. The work-scope manifest's
    own ``repos:`` and ``edges:`` (rare for repos, common for cross-suite
    edges) carry Source.WORK_SCOPE provenance so impact analyses can tell
    them apart from project-internal edges.
    """
    raw = read_manifest_raw(path)
    validate_header(raw, expected_kind=ManifestKind.WORK_SCOPE, path=path)
    _validate_platform_pin(raw)

    resolved = path.resolve()
    visited: frozenset[Path] = frozenset({resolved})

    # Apply includes — each include is a ProjectManifest, recursing through
    # _apply_project (which itself disallows includes via deprecation
    # warning under v0.9 and will hard-fail under v1.0).
    accumulated_nodes, accumulated_edges = _apply_includes(
        raw, path,
        accumulated_nodes,
        accumulated_edges,
        platform_node_ids=platform_node_ids,
        max_depth=max_depth,
        _visited=visited,
        _depth=1,
    )

    # Parse this work-scope's own nodes (rare, usually empty) with
    # WORK_SCOPE provenance so they're distinguishable from project nodes.
    work_scope_nodes = parse_nodes(raw, source=Source.WORK_SCOPE)
    work_scope_repo_ids = {n.repo_id for n in work_scope_nodes}

    platform_collisions = work_scope_repo_ids & platform_node_ids
    if platform_collisions:
        raise RepoGraphConfigError(
            f"WorkScopeManifest at {path} cannot redefine platform repo_id(s): "
            f"{sorted(platform_collisions)}"
        )
    sibling_collisions = work_scope_repo_ids & (
        set(accumulated_nodes.keys()) - platform_node_ids
    )
    if sibling_collisions:
        raise RepoGraphConfigError(
            f"WorkScopeManifest at {path} cannot redefine repo_id(s) "
            f"{sorted(sibling_collisions)} already declared by an included "
            f"project"
        )

    union_name_to_id: dict[str, str] = {}
    for node in (*accumulated_nodes.values(), *work_scope_nodes):
        union_name_to_id[node.canonical_name.lower()] = node.repo_id
        union_name_to_id[node.repo_id.lower()] = node.repo_id
        for alias in node.legacy_names:
            union_name_to_id[alias.lower()] = node.repo_id

    work_scope_edges = parse_edges(
        raw, name_to_id=union_name_to_id, source=Source.WORK_SCOPE
    )

    for edge in work_scope_edges:
        if edge.src in platform_node_ids and edge.dst in platform_node_ids:
            raise RepoGraphConfigError(
                f"WorkScopeManifest at {path} cannot add platform-to-platform "
                f"edge {edge.src} -> {edge.dst} ({edge.type.value})"
            )

    merged_nodes = dict(accumulated_nodes)
    for node in work_scope_nodes:
        merged_nodes[node.repo_id] = node

    return merged_nodes, list(accumulated_edges) + list(work_scope_edges)


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
