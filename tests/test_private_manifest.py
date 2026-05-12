# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 ProtocolWarden
"""Tests for the first-class private manifest surface."""

from __future__ import annotations

import json
from pathlib import Path

from platform_manifest import (
    EntityKind,
    ManifestKind,
    OntologyRelationshipKind,
    ProjectionBehavior,
    Visibility,
    load_effective_graph,
)
from platform_manifest.projection import to_public_manifest_dict
from platform_manifest.validate import validate_manifest


_PLATFORM_YAML = """\
manifest_kind: platform
manifest_version: "1.0.0"
repos:
  operations_center:
    canonical_name: OperationsCenter
    visibility: public
edges: []
"""


_PRIVATE_YAML = """\
manifest_kind: private
manifest_version: "1.0.0"
repos:
  managed_private_project:
    canonical_name: ManagedPrivateProject
    visibility: private
    kind: ManagedProject
    scope: managed_private_project
    projection_behavior: drop_from_public
    metadata:
      reference_testbed: true
  future_private_project:
    canonical_name: FutureManagedProject
    visibility: private
    kind: ManagedProject
    scope: managed_private_project
    projection_behavior: drop_from_public
  managed_private_project_public:
    canonical_name: ManagedProjectDocs
    visibility: public
    kind: PublicRepository
    projection_behavior: public_safe
    public_alias: ManagedProjectPublic
relationships:
  - id: public-docs-link
    source: ManagedProjectDocs
    target: OperationsCenter
    kind: documents
    visibility: public
    projection_behavior: public_safe
  - id: private-impl-link
    source: ManagedPrivateProject
    target: OperationsCenter
    kind: orchestrates
    visibility: private
    projection_behavior: drop_from_public
"""


def _write(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


def test_private_manifest_validates_and_supports_multiple_managed_projects(
    tmp_path: Path,
) -> None:
    private_path = _write(tmp_path, "private.yaml", _PRIVATE_YAML)
    report = validate_manifest(
        private_path,
        expected=ManifestKind.PRIVATE,
        against_platform=_write(tmp_path, "platform.yaml", _PLATFORM_YAML),
    )
    assert report.ok, [issue.to_dict() for issue in report.issues]


def test_effective_graph_accepts_private_manifest_layer(tmp_path: Path) -> None:
    graph = load_effective_graph(
        _write(tmp_path, "platform.yaml", _PLATFORM_YAML),
        private=_write(tmp_path, "private.yaml", _PRIVATE_YAML),
    )

    private_project = graph.resolve("ManagedPrivateProject")
    future = graph.resolve("FutureManagedProject")
    public = graph.resolve("ManagedProjectDocs")
    assert private_project is not None
    assert future is not None
    assert public is not None
    assert private_project.kind is EntityKind.MANAGED_PROJECT
    assert future.kind is EntityKind.MANAGED_PROJECT
    assert private_project.visibility is Visibility.PRIVATE
    assert future.visibility is Visibility.PRIVATE
    assert public.public_alias == "ManagedProjectPublic"

    docs_rels = graph.relationships_by_kind(OntologyRelationshipKind.DOCUMENTS)
    assert [rel.relationship_id for rel in docs_rels] == ["public-docs-link"]


def test_public_projection_derives_from_private_manifest_superset(tmp_path: Path) -> None:
    graph = load_effective_graph(
        _write(tmp_path, "platform.yaml", _PLATFORM_YAML),
        private=_write(tmp_path, "private.yaml", _PRIVATE_YAML),
    )

    projected = to_public_manifest_dict(graph)
    rendered = json.dumps(projected, sort_keys=True)
    repos = projected["repos"]

    assert "managed_private_project" not in repos
    assert "future_private_project" not in repos
    assert "managed_private_project_public" in repos
    assert repos["managed_private_project_public"]["canonical_name"] == "ManagedProjectPublic"
    assert "private-impl-link" not in rendered
    assert any(
        rel["id"] == "public-docs-link"
        and rel["projection_behavior"] == ProjectionBehavior.PUBLIC_SAFE.value
        for rel in projected["relationships"]
    )
    assert all(rel["id"] != "private-impl-link" for rel in projected["relationships"])


def test_private_only_relationship_never_projects_publicly(tmp_path: Path) -> None:
    graph = load_effective_graph(
        _write(tmp_path, "platform.yaml", _PLATFORM_YAML),
        private=_write(tmp_path, "private.yaml", _PRIVATE_YAML),
    )

    projected = to_public_manifest_dict(graph)
    assert all(
        rel["projection_behavior"] != ProjectionBehavior.PRIVATE_ONLY.value
        for rel in projected["relationships"]
    )
