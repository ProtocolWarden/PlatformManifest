# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 ProtocolWarden
"""Tests for first-class ontology relationships and projection metadata."""

from __future__ import annotations

from pathlib import Path

from platform_manifest import (
    OntologyRelationshipKind,
    ProjectionBehavior,
    Visibility,
    load_effective_graph,
)
from platform_manifest.projection import to_public_manifest_dict


_PLATFORM_YAML = """\
manifest_kind: platform
manifest_version: "1.0.0"
repos:
  operations_center:
    canonical_name: OperationsCenter
    visibility: public
    projection_behavior: public_safe
  executor_runtime:
    canonical_name: ExecutorRuntime
    visibility: public
    projection_behavior: public_safe
  hidden_public:
    canonical_name: HiddenPublic
    visibility: public
    projection_behavior: drop_from_public
relationships:
  - id: oc-orchestrates-er
    source: OperationsCenter
    target: ExecutorRuntime
    kind: orchestrates
    visibility: public
    projection_behavior: public_safe
  - id: hidden-rel
    source: HiddenPublic
    target: OperationsCenter
    kind: documents
    visibility: public
    projection_behavior: public_safe
edges: []
"""


def _write(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


def test_relationship_queries_are_first_class(tmp_path: Path) -> None:
    graph = load_effective_graph(_write(tmp_path, "platform.yaml", _PLATFORM_YAML))

    rels = graph.relationships_by_kind(OntologyRelationshipKind.ORCHESTRATES)
    assert [rel.relationship_id for rel in rels] == ["oc-orchestrates-er"]
    assert rels[0].visibility is Visibility.PUBLIC
    assert rels[0].projection_behavior is ProjectionBehavior.PUBLIC_SAFE
    assert [rel.relationship_id for rel in graph.relationships_from("operations_center")] == [
        "oc-orchestrates-er"
    ]
    assert [rel.relationship_id for rel in graph.relationships_to("executor_runtime")] == [
        "oc-orchestrates-er"
    ]


def test_projection_uses_explicit_projection_metadata(tmp_path: Path) -> None:
    graph = load_effective_graph(_write(tmp_path, "platform.yaml", _PLATFORM_YAML))
    projected = to_public_manifest_dict(graph)

    assert "hidden_public" not in projected["repos"]
    assert set(projected["repos"]) == {"operations_center", "executor_runtime"}
    assert [rel["id"] for rel in projected["relationships"]] == ["oc-orchestrates-er"]


def test_relationship_without_visibility_fails_closed(tmp_path: Path) -> None:
    bad = _write(
        tmp_path,
        "platform.yaml",
        'manifest_kind: platform\n'
        'manifest_version: "1.0.0"\n'
        'repos:\n'
        '  operations_center:\n'
        '    canonical_name: OperationsCenter\n'
        '    visibility: public\n'
        '  executor_runtime:\n'
        '    canonical_name: ExecutorRuntime\n'
        '    visibility: public\n'
        'relationships:\n'
        '  - id: bad-rel\n'
        '    source: OperationsCenter\n'
        '    target: ExecutorRuntime\n'
        '    kind: orchestrates\n'
        '    projection_behavior: public_safe\n'
        'edges: []\n',
    )
    from platform_manifest.validate import validate_manifest

    report = validate_manifest(bad)
    assert not report.ok
    assert any("visibility" in str(issue.to_dict()) for issue in report.issues)


def test_relationship_without_projection_behavior_fails_closed(tmp_path: Path) -> None:
    bad = _write(
        tmp_path,
        "platform.yaml",
        'manifest_kind: platform\n'
        'manifest_version: "1.0.0"\n'
        'repos:\n'
        '  operations_center:\n'
        '    canonical_name: OperationsCenter\n'
        '    visibility: public\n'
        '  executor_runtime:\n'
        '    canonical_name: ExecutorRuntime\n'
        '    visibility: public\n'
        'relationships:\n'
        '  - id: bad-rel\n'
        '    source: OperationsCenter\n'
        '    target: ExecutorRuntime\n'
        '    kind: orchestrates\n'
        '    visibility: public\n'
        'edges: []\n',
    )
    from platform_manifest.validate import validate_manifest

    report = validate_manifest(bad)
    assert not report.ok
    assert any("projection_behavior" in str(issue.to_dict()) for issue in report.issues)
