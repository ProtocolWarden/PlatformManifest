# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Velascat
"""Tests for WorkScopeManifest (manifest_kind: work_scope) — v0.9.0+.

WorkScopeManifest is the explicit multi-project composition layer.
Replaces the v0.8.x project-shell-with-includes pattern, which was
deprecated in v0.9.x and removed in v1.0.0.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from platform_manifest import (
    ManifestKind,
    RepoGraphConfigError,
    Source,
    Visibility,
    load_effective_graph,
)


_PLATFORM_YAML = """\
manifest_kind: platform
manifest_version: "1.0.0"

repos:
  operations_center:
    canonical_name: OperationsCenter
    visibility: public
    runtime_role: orchestration
  source_registry:
    canonical_name: SourceRegistry
    visibility: public
    runtime_role: fork_management
  rxp:
    canonical_name: RxP
    visibility: public
    runtime_role: contracts

edges:
  - {from: OperationsCenter, to: SourceRegistry, type: dispatches_to}
"""


@pytest.fixture
def platform_path(tmp_path: Path) -> Path:
    p = tmp_path / "platform.yaml"
    p.write_text(_PLATFORM_YAML, encoding="utf-8")
    return p


def _project_a(tmp_path: Path) -> Path:
    p = tmp_path / "project_a.yaml"
    p.write_text(
        'manifest_kind: project\n'
        'manifest_version: "1.0.0"\n'
        'repos:\n'
        '  proj_a_api:\n'
        '    canonical_name: ProjectAAPI\n'
        '    visibility: private\n'
        '    runtime_role: project_service\n'
        'edges:\n'
        '  - {from: ProjectAAPI, to: RxP, type: depends_on_contracts_from}\n',
        encoding="utf-8",
    )
    return p


def _project_b(tmp_path: Path) -> Path:
    p = tmp_path / "project_b.yaml"
    p.write_text(
        'manifest_kind: project\n'
        'manifest_version: "1.0.0"\n'
        'repos:\n'
        '  proj_b_worker:\n'
        '    canonical_name: ProjectBWorker\n'
        '    visibility: private\n'
        '    runtime_role: artifact_worker\n'
        'edges:\n'
        '  - {from: ProjectBWorker, to: ProjectAAPI, type: dispatches_to}\n',
        encoding="utf-8",
    )
    return p


# ---------------------------------------------------------------------------
# Positive paths
# ---------------------------------------------------------------------------


class TestWorkScopeBasic:
    def test_work_scope_composes_two_projects(
        self, platform_path: Path, tmp_path: Path
    ) -> None:
        proj_a = _project_a(tmp_path)
        proj_b = _project_b(tmp_path)
        ws = tmp_path / "work_scope.yaml"
        ws.write_text(
            'manifest_kind: work_scope\n'
            'manifest_version: "1.0.0"\n'
            'includes:\n'
            f'  - {{name: ProjectA, project_manifest_path: {proj_a}}}\n'
            f'  - {{name: ProjectB, project_manifest_path: {proj_b}}}\n',
            encoding="utf-8",
        )
        g = load_effective_graph(platform_path, work_scope=ws)
        ids = {n.repo_id for n in g.list_nodes()}
        assert "proj_a_api" in ids
        assert "proj_b_worker" in ids
        # Included projects keep PROJECT provenance
        a = g.resolve("ProjectAAPI")
        b = g.resolve("ProjectBWorker")
        assert a is not None and a.source is Source.PROJECT
        assert b is not None and b.source is Source.PROJECT
        # Cross-suite project edge survives
        edge_ids = {(e.src, e.dst, e.type.value) for e in g.edges}
        assert ("proj_b_worker", "proj_a_api", "dispatches_to") in edge_ids

    def test_work_scope_own_edges_carry_work_scope_provenance(
        self, platform_path: Path, tmp_path: Path
    ) -> None:
        proj_a = _project_a(tmp_path)
        ws = tmp_path / "work_scope.yaml"
        ws.write_text(
            'manifest_kind: work_scope\n'
            'manifest_version: "1.0.0"\n'
            'includes:\n'
            f'  - {{name: ProjectA, project_manifest_path: {proj_a}}}\n'
            'edges:\n'
            '  - {from: OperationsCenter, to: ProjectAAPI, type: dispatches_to}\n',
            encoding="utf-8",
        )
        g = load_effective_graph(platform_path, work_scope=ws)
        ws_edge = next(
            e for e in g.edges
            if e.src == "operations_center" and e.dst == "proj_a_api"
        )
        assert ws_edge.source is Source.WORK_SCOPE


# ---------------------------------------------------------------------------
# Slot validation
# ---------------------------------------------------------------------------


class TestSlotValidation:
    def test_project_in_work_scope_slot_fails(
        self, platform_path: Path, tmp_path: Path
    ) -> None:
        proj = _project_a(tmp_path)
        with pytest.raises(RepoGraphConfigError, match="manifest_kind"):
            load_effective_graph(platform_path, work_scope=proj)

    def test_work_scope_in_project_slot_fails(
        self, platform_path: Path, tmp_path: Path
    ) -> None:
        proj_a = _project_a(tmp_path)
        ws = tmp_path / "work_scope.yaml"
        ws.write_text(
            'manifest_kind: work_scope\n'
            'manifest_version: "1.0.0"\n'
            'includes:\n'
            f'  - {{name: ProjectA, project_manifest_path: {proj_a}}}\n',
            encoding="utf-8",
        )
        with pytest.raises(RepoGraphConfigError, match="manifest_kind"):
            load_effective_graph(platform_path, project=ws)

    def test_project_and_work_scope_mutually_exclusive(
        self, platform_path: Path, tmp_path: Path
    ) -> None:
        proj_a = _project_a(tmp_path)
        ws = tmp_path / "work_scope.yaml"
        ws.write_text(
            'manifest_kind: work_scope\n'
            'manifest_version: "1.0.0"\n'
            'includes:\n'
            f'  - {{name: ProjectA, project_manifest_path: {proj_a}}}\n',
            encoding="utf-8",
        )
        with pytest.raises(RepoGraphConfigError, match="mutually exclusive"):
            load_effective_graph(platform_path, project=proj_a, work_scope=ws)


# ---------------------------------------------------------------------------
# Architecture invariants — work scope cannot mutate platform
# ---------------------------------------------------------------------------


class TestPlatformImmutability:
    def test_work_scope_cannot_redefine_platform_node(
        self, platform_path: Path, tmp_path: Path
    ) -> None:
        ws = tmp_path / "work_scope.yaml"
        ws.write_text(
            'manifest_kind: work_scope\n'
            'manifest_version: "1.0.0"\n'
            'includes: []\n'
            'repos:\n'
            '  operations_center:\n'
            '    canonical_name: OperationsCenter\n'
            '    visibility: private\n',
            encoding="utf-8",
        )
        # Schema requires minItems:1 for includes — bypass via direct
        # composer call would surface platform collision; here the
        # schema layer rejects empty includes first.
        # Use a stub include to get past schema, then collision triggers.
        proj_a = _project_a(tmp_path)
        ws.write_text(
            'manifest_kind: work_scope\n'
            'manifest_version: "1.0.0"\n'
            'includes:\n'
            f'  - {{name: ProjectA, project_manifest_path: {proj_a}}}\n'
            'repos:\n'
            '  operations_center:\n'
            '    canonical_name: OperationsCenter\n'
            '    visibility: private\n',
            encoding="utf-8",
        )
        with pytest.raises(RepoGraphConfigError, match="redefine platform"):
            load_effective_graph(platform_path, work_scope=ws)

    def test_work_scope_cannot_add_platform_to_platform_edge(
        self, platform_path: Path, tmp_path: Path
    ) -> None:
        proj_a = _project_a(tmp_path)
        ws = tmp_path / "work_scope.yaml"
        ws.write_text(
            'manifest_kind: work_scope\n'
            'manifest_version: "1.0.0"\n'
            'includes:\n'
            f'  - {{name: ProjectA, project_manifest_path: {proj_a}}}\n'
            'edges:\n'
            '  - {from: OperationsCenter, to: RxP, type: dispatches_to}\n',
            encoding="utf-8",
        )
        with pytest.raises(RepoGraphConfigError, match="platform-to-platform"):
            load_effective_graph(platform_path, work_scope=ws)


# ---------------------------------------------------------------------------
# Visibility — work scope does not widen
# ---------------------------------------------------------------------------


class TestVisibilityPreservation:
    def test_private_project_nodes_stay_private(
        self, platform_path: Path, tmp_path: Path
    ) -> None:
        proj_a = _project_a(tmp_path)
        ws = tmp_path / "work_scope.yaml"
        ws.write_text(
            'manifest_kind: work_scope\n'
            'manifest_version: "1.0.0"\n'
            'includes:\n'
            f'  - {{name: ProjectA, project_manifest_path: {proj_a}}}\n',
            encoding="utf-8",
        )
        g = load_effective_graph(platform_path, work_scope=ws)
        a = g.resolve("ProjectAAPI")
        assert a is not None
        assert a.visibility is Visibility.PRIVATE


# ---------------------------------------------------------------------------
# v1.0.0 hard enforcement — project manifests cannot include
# ---------------------------------------------------------------------------


class TestProjectIncludesRejected:
    def test_project_with_includes_hard_fails(
        self, platform_path: Path, tmp_path: Path
    ) -> None:
        proj_a = _project_a(tmp_path)
        legacy_shell = tmp_path / "legacy_shell.yaml"
        legacy_shell.write_text(
            'manifest_kind: project\n'
            'manifest_version: "1.0.0"\n'
            'includes:\n'
            f'  - {{name: ProjectA, project_manifest_path: {proj_a}}}\n',
            encoding="utf-8",
        )
        # Loader path: rejected via the explicit migration-hint guard
        with pytest.raises(RepoGraphConfigError, match="work_scope"):
            load_effective_graph(platform_path, project=legacy_shell)


# ---------------------------------------------------------------------------
# Cycle + collision rules carry over
# ---------------------------------------------------------------------------


class TestCompositionRules:
    def test_collision_between_two_includes_rejected(
        self, platform_path: Path, tmp_path: Path
    ) -> None:
        proj_a = _project_a(tmp_path)
        # second project re-declares proj_a_api
        proj_dup = tmp_path / "project_dup.yaml"
        proj_dup.write_text(
            'manifest_kind: project\n'
            'manifest_version: "1.0.0"\n'
            'repos:\n'
            '  proj_a_api:\n'
            '    canonical_name: ProjectAAPIClone\n'
            '    visibility: private\n',
            encoding="utf-8",
        )
        ws = tmp_path / "work_scope.yaml"
        ws.write_text(
            'manifest_kind: work_scope\n'
            'manifest_version: "1.0.0"\n'
            'includes:\n'
            f'  - {{name: A, project_manifest_path: {proj_a}}}\n'
            f'  - {{name: ADup, project_manifest_path: {proj_dup}}}\n',
            encoding="utf-8",
        )
        with pytest.raises(RepoGraphConfigError, match="already declared"):
            load_effective_graph(platform_path, work_scope=ws)

    def test_manifest_kind_enum_carries_work_scope(self) -> None:
        assert ManifestKind("work_scope") is ManifestKind.WORK_SCOPE
        assert ManifestKind.WORK_SCOPE.value == "work_scope"

    def test_source_enum_carries_work_scope(self) -> None:
        assert Source("work_scope") is Source.WORK_SCOPE


# ---------------------------------------------------------------------------
# Local annotates work-scope-composed graph
# ---------------------------------------------------------------------------


class TestLocalOverWorkScope:
    def test_local_annotates_included_project_node(
        self, platform_path: Path, tmp_path: Path
    ) -> None:
        proj_a = _project_a(tmp_path)
        ws = tmp_path / "work_scope.yaml"
        ws.write_text(
            'manifest_kind: work_scope\n'
            'manifest_version: "1.0.0"\n'
            'includes:\n'
            f'  - {{name: ProjectA, project_manifest_path: {proj_a}}}\n',
            encoding="utf-8",
        )
        local = tmp_path / "local.yaml"
        local.write_text(
            'manifest_kind: local\n'
            'manifest_version: "1.0.0"\n'
            'repos:\n'
            '  proj_a_api:\n'
            '    local_path: /home/dev/src/ProjectA\n'
            '    local_port: 9090\n',
            encoding="utf-8",
        )
        g = load_effective_graph(platform_path, work_scope=ws, local=local)
        a = g.resolve("ProjectAAPI")
        assert a is not None
        assert a.local_path == "/home/dev/src/ProjectA"
        assert a.local_port == 9090
        # Provenance unchanged by local layer
        assert a.source is Source.PROJECT
