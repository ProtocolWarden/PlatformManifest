# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Velascat
"""Composition tests — PlatformManifest + ProjectManifest + LocalManifest.

Covers the four worked failure examples from the design doc plus the
positive paths (project nodes attach, local annotations apply, edges
dedupe, version_constraint validation).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from platform_manifest import (
    RepoGraphConfigError,
    Source,
    Visibility,
    load_effective_graph,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


_PLATFORM_YAML = """\
manifest_kind: platform
manifest_version: "1.0.0"

repos:
  operations_center:
    canonical_name: OperationsCenter
    visibility: public
    runtime_role: orchestration
  switchboard:
    canonical_name: SwitchBoard
    visibility: public
    runtime_role: lane_selection
  source_registry:
    canonical_name: SourceRegistry
    visibility: public
    runtime_role: fork_management
  rxp:
    canonical_name: RxP
    visibility: public
    runtime_role: contracts

edges:
  - {from: OperationsCenter, to: SwitchBoard, type: routes_through}
  - {from: OperationsCenter, to: SourceRegistry, type: dispatches_to}
"""


@pytest.fixture
def platform_path(tmp_path: Path) -> Path:
    p = tmp_path / "platform.yaml"
    p.write_text(_PLATFORM_YAML, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Positive paths
# ---------------------------------------------------------------------------


class TestPlatformOnly:
    def test_loads_platform_only(self, platform_path: Path) -> None:
        g = load_effective_graph(platform_path)
        assert {n.repo_id for n in g.list_nodes()} == {
            "operations_center",
            "switchboard",
            "source_registry",
            "rxp",
        }
        for node in g.list_nodes():
            assert node.source is Source.PLATFORM


class TestProjectAttaches:
    def test_project_adds_private_nodes_and_edges(
        self, platform_path: Path, tmp_path: Path
    ) -> None:
        proj = tmp_path / "project.yaml"
        proj.write_text(
            'manifest_kind: project\n'
            'manifest_version: "1.0.0"\n'
            'repos:\n'
            '  generic_repo_a:\n'
            '    canonical_name: GenericRepoA\n'
            '    visibility: private\n'
            '    runtime_role: project_service\n'
            '  generic_repo_b:\n'
            '    canonical_name: GenericRepoB\n'
            '    visibility: private\n'
            '    runtime_role: artifact_worker\n'
            'edges:\n'
            '  - {from: GenericRepoA, to: OperationsCenter, type: dispatches_to}\n'
            '  - {from: GenericRepoB, to: RxP, type: depends_on_contracts_from}\n',
            encoding="utf-8",
        )
        g = load_effective_graph(platform_path, project=proj)
        ids = {n.repo_id for n in g.list_nodes()}
        assert "generic_repo_a" in ids
        assert "generic_repo_b" in ids
        # Provenance
        node_a = g.resolve("GenericRepoA")
        assert node_a is not None
        assert node_a.source is Source.PROJECT
        assert node_a.visibility is Visibility.PRIVATE
        # OC stays platform
        oc = g.resolve("OperationsCenter")
        assert oc.source is Source.PLATFORM
        # Project edge into platform survives
        oc_inbound = {e.src for e in g.edges if e.dst == "operations_center"}
        assert "generic_repo_a" in oc_inbound


class TestLocalAnnotates:
    def test_local_attaches_local_path_and_port(
        self, platform_path: Path, tmp_path: Path
    ) -> None:
        local = tmp_path / "local.yaml"
        local.write_text(
            'manifest_kind: local\n'
            'manifest_version: "1.0.0"\n'
            'repos:\n'
            '  operations_center:\n'
            '    local_path: /home/dev/src/OperationsCenter\n'
            '    local_port: 8080\n'
            '  rxp:\n'
            '    cache_path: /tmp/rxp-cache\n'
            '    gpu_required: false\n',
            encoding="utf-8",
        )
        g = load_effective_graph(platform_path, local=local)
        oc = g.resolve("OperationsCenter")
        assert oc.local_path == "/home/dev/src/OperationsCenter"
        assert oc.local_port == 8080
        # Provenance unchanged — local doesn't introduce nodes.
        assert oc.source is Source.PLATFORM
        rxp = g.resolve("RxP")
        assert rxp.cache_path == "/tmp/rxp-cache"
        assert rxp.gpu_required is False

    def test_local_runtime_hints_normalize(
        self, platform_path: Path, tmp_path: Path
    ) -> None:
        local = tmp_path / "local.yaml"
        local.write_text(
            'manifest_kind: local\n'
            'manifest_version: "1.0.0"\n'
            'repos:\n'
            '  operations_center:\n'
            '    runtime_hints:\n'
            '      memory_limit_mb: 2048\n'
            '      use_jit: true\n'
            '      tier: standard\n',
            encoding="utf-8",
        )
        g = load_effective_graph(platform_path, local=local)
        oc = g.resolve("OperationsCenter")
        hints = dict(oc.runtime_hints)
        assert hints == {"memory_limit_mb": 2048, "use_jit": True, "tier": "standard"}


class TestEdgeDedup:
    def test_duplicate_edge_is_deduped(
        self, platform_path: Path, tmp_path: Path
    ) -> None:
        # Project replays an edge that already exists in the platform graph.
        # In a real project this wouldn't happen since project edges
        # involving two platform repos are forbidden — but a project repo
        # → platform edge that the project also re-asserts via a second
        # edges row should still dedupe within the project layer.
        proj = tmp_path / "project.yaml"
        proj.write_text(
            'manifest_kind: project\n'
            'manifest_version: "1.0.0"\n'
            'repos:\n'
            '  generic_repo_a:\n'
            '    canonical_name: GenericRepoA\n'
            '    visibility: private\n'
            'edges:\n'
            '  - {from: GenericRepoA, to: OperationsCenter, type: dispatches_to}\n'
            '  - {from: GenericRepoA, to: OperationsCenter, type: dispatches_to}\n',
            encoding="utf-8",
        )
        g = load_effective_graph(platform_path, project=proj)
        same = [
            e for e in g.edges
            if e.src == "generic_repo_a" and e.dst == "operations_center"
        ]
        assert len(same) == 1

    def test_different_edge_types_between_same_pair_kept(
        self, platform_path: Path, tmp_path: Path
    ) -> None:
        proj = tmp_path / "project.yaml"
        proj.write_text(
            'manifest_kind: project\n'
            'manifest_version: "1.0.0"\n'
            'repos:\n'
            '  generic_repo_a:\n'
            '    canonical_name: GenericRepoA\n'
            '    visibility: private\n'
            'edges:\n'
            '  - {from: GenericRepoA, to: OperationsCenter, type: dispatches_to}\n'
            '  - {from: GenericRepoA, to: OperationsCenter, type: depends_on_contracts_from}\n',
            encoding="utf-8",
        )
        g = load_effective_graph(platform_path, project=proj)
        kinds = {
            e.type.value for e in g.edges
            if e.src == "generic_repo_a" and e.dst == "operations_center"
        }
        assert kinds == {"dispatches_to", "depends_on_contracts_from"}


# ---------------------------------------------------------------------------
# Failure 1 — PlatformManifest contains private node (covered in test_repo_graph too)
# ---------------------------------------------------------------------------


class TestFailure1:
    def test_platform_with_private_node_rejected(self, tmp_path: Path) -> None:
        bad = tmp_path / "platform.yaml"
        bad.write_text(
            'manifest_kind: platform\n'
            'manifest_version: "1.0.0"\n'
            'repos:\n'
            '  oc: {canonical_name: OperationsCenter, visibility: public}\n'
            '  ga: {canonical_name: GenericRepoA, visibility: private}\n',
            encoding="utf-8",
        )
        with pytest.raises(RepoGraphConfigError, match="public nodes"):
            load_effective_graph(bad)


# ---------------------------------------------------------------------------
# Failure 2 — ProjectManifest redefines platform node
# ---------------------------------------------------------------------------


class TestFailure2:
    def test_project_redefining_platform_repo_rejected(
        self, platform_path: Path, tmp_path: Path
    ) -> None:
        proj = tmp_path / "project.yaml"
        proj.write_text(
            'manifest_kind: project\n'
            'manifest_version: "1.0.0"\n'
            'repos:\n'
            '  operations_center:\n'
            '    canonical_name: MyCustomOperationsCenter\n'
            '    visibility: private\n',
            encoding="utf-8",
        )
        with pytest.raises(RepoGraphConfigError, match="cannot redefine platform repo_id"):
            load_effective_graph(platform_path, project=proj)


# ---------------------------------------------------------------------------
# Failure 3 — ProjectManifest adds platform-to-platform edge
# ---------------------------------------------------------------------------


class TestFailure3:
    def test_project_platform_to_platform_edge_rejected(
        self, platform_path: Path, tmp_path: Path
    ) -> None:
        proj = tmp_path / "project.yaml"
        proj.write_text(
            'manifest_kind: project\n'
            'manifest_version: "1.0.0"\n'
            'edges:\n'
            '  - {from: OperationsCenter, to: SourceRegistry, type: routes_through}\n',
            encoding="utf-8",
        )
        with pytest.raises(RepoGraphConfigError, match="platform-to-platform edge"):
            load_effective_graph(platform_path, project=proj)


# ---------------------------------------------------------------------------
# Failure 4 — LocalManifest tries to change canonical identity
# ---------------------------------------------------------------------------


class TestFailure4:
    def test_local_with_canonical_name_rejected(
        self, platform_path: Path, tmp_path: Path
    ) -> None:
        local = tmp_path / "local.yaml"
        local.write_text(
            'manifest_kind: local\n'
            'manifest_version: "1.0.0"\n'
            'repos:\n'
            '  operations_center:\n'
            '    canonical_name: MyLocalOC\n',
            encoding="utf-8",
        )
        with pytest.raises(RepoGraphConfigError, match="not allowed"):
            load_effective_graph(platform_path, local=local)

    def test_local_with_visibility_rejected(
        self, platform_path: Path, tmp_path: Path
    ) -> None:
        local = tmp_path / "local.yaml"
        local.write_text(
            'manifest_kind: local\n'
            'manifest_version: "1.0.0"\n'
            'repos:\n'
            '  operations_center:\n'
            '    visibility: private\n',
            encoding="utf-8",
        )
        with pytest.raises(RepoGraphConfigError, match="not allowed"):
            load_effective_graph(platform_path, local=local)


# ---------------------------------------------------------------------------
# LocalManifest extra rules
# ---------------------------------------------------------------------------


class TestLocalRules:
    def test_local_unknown_repo_id_rejected(
        self, platform_path: Path, tmp_path: Path
    ) -> None:
        local = tmp_path / "local.yaml"
        local.write_text(
            'manifest_kind: local\n'
            'manifest_version: "1.0.0"\n'
            'repos:\n'
            '  ghost_service:\n'
            '    local_path: /tmp/ghost\n',
            encoding="utf-8",
        )
        with pytest.raises(RepoGraphConfigError, match="unknown repo_id"):
            load_effective_graph(platform_path, local=local)

    def test_local_port_out_of_range_rejected(
        self, platform_path: Path, tmp_path: Path
    ) -> None:
        local = tmp_path / "local.yaml"
        local.write_text(
            'manifest_kind: local\n'
            'manifest_version: "1.0.0"\n'
            'repos:\n'
            '  operations_center:\n'
            '    local_port: 99999\n',
            encoding="utf-8",
        )
        with pytest.raises(RepoGraphConfigError, match="local_port"):
            load_effective_graph(platform_path, local=local)


# ---------------------------------------------------------------------------
# Slot mismatch — wrong manifest_kind in wrong slot
# ---------------------------------------------------------------------------


class TestSlotMismatch:
    def test_local_in_project_slot_rejected(
        self, platform_path: Path, tmp_path: Path
    ) -> None:
        bad = tmp_path / "wrong.yaml"
        bad.write_text(
            'manifest_kind: local\n'
            'manifest_version: "1.0.0"\n',
            encoding="utf-8",
        )
        with pytest.raises(RepoGraphConfigError, match="expected manifest_kind='project'"):
            load_effective_graph(platform_path, project=bad)

    def test_platform_in_local_slot_rejected(
        self, platform_path: Path, tmp_path: Path
    ) -> None:
        bad = tmp_path / "wrong.yaml"
        bad.write_text(
            'manifest_kind: platform\n'
            'manifest_version: "1.0.0"\n',
            encoding="utf-8",
        )
        with pytest.raises(RepoGraphConfigError, match="expected manifest_kind='local'"):
            load_effective_graph(platform_path, local=bad)


# ---------------------------------------------------------------------------
# version_constraint
# ---------------------------------------------------------------------------


class TestVersionConstraint:
    def test_satisfied_constraint_loads(
        self, platform_path: Path, tmp_path: Path
    ) -> None:
        # The installed PM version is 0.3.x (this branch). >=0.1 is always satisfied.
        proj = tmp_path / "project.yaml"
        proj.write_text(
            'manifest_kind: project\n'
            'manifest_version: "1.0.0"\n'
            'platform_manifest:\n'
            '  name: PlatformManifest\n'
            '  version_constraint: ">=0.1"\n',
            encoding="utf-8",
        )
        g = load_effective_graph(platform_path, project=proj)
        assert g.resolve("OperationsCenter") is not None

    def test_unsatisfied_constraint_rejected(
        self, platform_path: Path, tmp_path: Path
    ) -> None:
        proj = tmp_path / "project.yaml"
        proj.write_text(
            'manifest_kind: project\n'
            'manifest_version: "1.0.0"\n'
            'platform_manifest:\n'
            '  name: PlatformManifest\n'
            '  version_constraint: ">=99.0"\n',
            encoding="utf-8",
        )
        with pytest.raises(RepoGraphConfigError, match="does not satisfy"):
            load_effective_graph(platform_path, project=proj)

    def test_invalid_constraint_rejected(
        self, platform_path: Path, tmp_path: Path
    ) -> None:
        proj = tmp_path / "project.yaml"
        proj.write_text(
            'manifest_kind: project\n'
            'manifest_version: "1.0.0"\n'
            'platform_manifest:\n'
            '  name: PlatformManifest\n'
            '  version_constraint: "not-a-pep440"\n',
            encoding="utf-8",
        )
        with pytest.raises(RepoGraphConfigError, match="PEP 440"):
            load_effective_graph(platform_path, project=proj)


# ---------------------------------------------------------------------------
# Local-only field leakage check on platform/project layers
# ---------------------------------------------------------------------------


class TestLocalFieldLeakage:
    def test_platform_with_local_field_rejected(self, tmp_path: Path) -> None:
        bad = tmp_path / "platform.yaml"
        bad.write_text(
            'manifest_kind: platform\n'
            'manifest_version: "1.0.0"\n'
            'repos:\n'
            '  oc:\n'
            '    canonical_name: OperationsCenter\n'
            '    visibility: public\n'
            '    local_path: /home/dave/oc\n',
            encoding="utf-8",
        )
        with pytest.raises(RepoGraphConfigError, match="local-only field"):
            load_effective_graph(bad)

    def test_project_with_local_field_rejected(
        self, platform_path: Path, tmp_path: Path
    ) -> None:
        proj = tmp_path / "project.yaml"
        proj.write_text(
            'manifest_kind: project\n'
            'manifest_version: "1.0.0"\n'
            'repos:\n'
            '  vf:\n'
            '    canonical_name: GenericRepoA\n'
            '    visibility: private\n'
            '    cache_path: /tmp/vf\n',
            encoding="utf-8",
        )
        with pytest.raises(RepoGraphConfigError, match="local-only field"):
            load_effective_graph(platform_path, project=proj)
