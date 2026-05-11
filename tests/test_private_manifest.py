# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 ProtocolWarden
"""Tests for the first-class PrivateManifest surface."""

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
  video_foundry:
    canonical_name: VideoFoundry
    visibility: private
    kind: ManagedProject
    scope: managed_private_project
    projection_behavior: drop_from_public
    metadata:
      reference_testbed: true
  future_private_project:
    canonical_name: FuturePrivateProject
    visibility: private
    kind: ManagedProject
    scope: managed_private_project
    projection_behavior: drop_from_public
  video_foundry_public:
    canonical_name: VideoFoundryDocs
    visibility: public
    kind: PublicRepository
    projection_behavior: public_safe
    public_alias: VideoFoundryPublic
relationships:
  - id: vf-public-docs
    source: VideoFoundryDocs
    target: OperationsCenter
    kind: documents
    visibility: public
    projection_behavior: public_safe
  - id: vf-private-impl
    source: VideoFoundry
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

    vf = graph.resolve("VideoFoundry")
    future = graph.resolve("FuturePrivateProject")
    public = graph.resolve("VideoFoundryDocs")
    assert vf is not None
    assert future is not None
    assert public is not None
    assert vf.kind is EntityKind.MANAGED_PROJECT
    assert future.kind is EntityKind.MANAGED_PROJECT
    assert vf.visibility is Visibility.PRIVATE
    assert future.visibility is Visibility.PRIVATE
    assert public.public_alias == "VideoFoundryPublic"

    docs_rels = graph.relationships_by_kind(OntologyRelationshipKind.DOCUMENTS)
    assert [rel.relationship_id for rel in docs_rels] == ["vf-public-docs"]


def test_public_projection_derives_from_private_manifest_superset(tmp_path: Path) -> None:
    graph = load_effective_graph(
        _write(tmp_path, "platform.yaml", _PLATFORM_YAML),
        private=_write(tmp_path, "private.yaml", _PRIVATE_YAML),
    )

    projected = to_public_manifest_dict(graph)
    rendered = json.dumps(projected, sort_keys=True)
    repos = projected["repos"]

    assert "video_foundry" not in repos
    assert "future_private_project" not in repos
    assert "video_foundry_public" in repos
    assert repos["video_foundry_public"]["canonical_name"] == "VideoFoundryPublic"
    assert "vf-private-impl" not in rendered
    assert any(
        rel["id"] == "vf-public-docs"
        and rel["projection_behavior"] == ProjectionBehavior.PUBLIC_SAFE.value
        for rel in projected["relationships"]
    )
    assert all(rel["id"] != "vf-private-impl" for rel in projected["relationships"])


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
