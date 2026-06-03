# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 ProtocolWarden
"""Public projection tests."""

from __future__ import annotations

import json
from pathlib import Path

from platform_manifest import load_effective_graph, to_public_manifest_dict
from platform_manifest.validate import validate_manifest


_PLATFORM_YAML = """\
manifest_kind: platform
manifest_version: "1.0.0"
repos:
  operations_center:
    canonical_name: OperationsCenter
    visibility: public
    owner: ProtocolWarden
    scope: platform
  public_docs:
    canonical_name: PublicDocs
    visibility: public
edges:
  - {from: OperationsCenter, to: PublicDocs, type: dispatches_to}
"""


_PROJECT_YAML = """\
manifest_kind: project
manifest_version: "1.0.0"
repos:
  private_impl:
    canonical_name: PrivateImpl
    visibility: private
    kind: ManagedRepository
    owner: ProtocolWarden
    scope: private_project
    github_url: https://github.com/private/private-impl
    metadata:
      internal_path: /home/dev/private/private-impl
  public_project_docs:
    canonical_name: PublicProjectDocs
    visibility: public
    kind: PublicRepository
    metadata:
      docs_url: https://github.com/ProtocolWarden/PublicProjectDocs
edges:
  - {from: PrivateImpl, to: OperationsCenter, type: dispatches_to}
  - {from: PublicProjectDocs, to: OperationsCenter, type: depends_on_contracts_from}
"""


_LOCAL_YAML = """\
manifest_kind: local
manifest_version: "1.0.0"
repos:
  operations_center:
    local_path: /home/dev/private/OperationsCenter
    env_file: /home/dev/private/.env
    endpoint_override: http://127.0.0.1:8080
  private_impl:
    local_path: /home/dev/private/private-impl
    runtime_hints:
      secret_lane: local-only
"""


def _write(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


def test_public_projection_drops_private_nodes_edges_and_local_fields(
    tmp_path: Path,
) -> None:
    graph = load_effective_graph(
        _write(tmp_path, "platform.yaml", _PLATFORM_YAML),
        project=_write(tmp_path, "project.yaml", _PROJECT_YAML),
        local=_write(tmp_path, "local.yaml", _LOCAL_YAML),
    )

    projected = to_public_manifest_dict(graph)
    rendered = json.dumps(projected, sort_keys=True)

    assert set(projected["repos"]) == {
        "operations_center",
        "public_docs",
        "public_project_docs",
    }
    assert "private_impl" not in projected["repos"]
    assert "PrivateImpl" not in rendered
    assert "github.com/private" not in rendered
    assert "/home/dev/private" not in rendered
    assert "env_file" not in rendered
    assert "endpoint_override" not in rendered
    assert "runtime_hints" not in rendered
    assert all(
        edge["from"] in projected["repos"] and edge["to"] in projected["repos"]
        for edge in projected["edges"]
    )


def test_public_projection_validates_as_platform_manifest(tmp_path: Path) -> None:
    graph = load_effective_graph(
        _write(tmp_path, "platform.yaml", _PLATFORM_YAML),
        project=_write(tmp_path, "project.yaml", _PROJECT_YAML),
    )
    projected = to_public_manifest_dict(graph)

    path = tmp_path / "public_projection.json"
    path.write_text(json.dumps(projected), encoding="utf-8")
    report = validate_manifest(path)

    assert report.ok, [issue.to_dict() for issue in report.issues]
