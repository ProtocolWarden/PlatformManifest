# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Velascat
"""Multi-project composition via shell-repo pattern (R6).

A project manifest may declare `includes: [...]`, each item pointing
at another project_manifest.yaml. The loader recurses, applying each
included sub-project's nodes/edges before the including project's own.

Collision rules:
- Duplicate repo_id between a sub-project and the platform → hard fail
- Duplicate repo_id between sibling sub-projects → hard fail
- Cycles (A includes B includes A) → hard fail
- Cross-include edges (sub-project A references sub-project B's node) → allowed
- Visibility never widens (private stays private across composition)
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


_PLATFORM_YAML = """\
manifest_kind: platform
manifest_version: "1.0.0"
repos:
  operations_center:
    canonical_name: OperationsCenter
    visibility: public
    runtime_role: orchestration
  cxrp:
    canonical_name: CxRP
    visibility: public
    runtime_role: contracts
edges:
  - {from: OperationsCenter, to: CxRP, type: depends_on_contracts_from}
"""


@pytest.fixture
def platform(tmp_path: Path) -> Path:
    p = tmp_path / "platform.yaml"
    p.write_text(_PLATFORM_YAML, encoding="utf-8")
    return p


def _write_project(
    path: Path, *, repos: list[dict], edges: list[dict] | None = None,
    includes: list[dict] | None = None,
) -> None:
    """Helper to write a project manifest with given content."""
    import yaml
    body: dict = {
        "manifest_kind": "project",
        "manifest_version": "1.0.0",
        "repos": {r["repo_id"]: {k: v for k, v in r.items() if k != "repo_id"}
                  for r in repos},
    }
    if edges:
        body["edges"] = edges
    if includes:
        body["includes"] = includes
    path.write_text(yaml.safe_dump(body, sort_keys=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


class TestSingleInclude:
    def test_shell_includes_one_subproject(
        self, tmp_path: Path, platform: Path
    ) -> None:
        sub = tmp_path / "sub.yaml"
        _write_project(
            sub,
            repos=[{
                "repo_id": "vfa",
                "canonical_name": "VFAApi",
                "visibility": "private",
            }],
            edges=[{"from": "VFAApi", "to": "OperationsCenter", "type": "dispatches_to"}],
        )
        shell = tmp_path / "shell.yaml"
        _write_project(
            shell,
            repos=[],
            includes=[{"name": "VFA", "project_manifest_path": "sub.yaml"}],
        )

        g = load_effective_graph(platform, project=shell)

        # Sub-project node lands in the merged graph
        vfa = g.resolve("VFAApi")
        assert vfa is not None
        assert vfa.source is Source.PROJECT
        assert vfa.visibility is Visibility.PRIVATE

        # Sub-project edge lands too
        assert any(
            e.src == "vfa" and e.dst == "operations_center"
            and e.type.value == "dispatches_to"
            for e in g.edges
        )


class TestMultipleIncludes:
    def test_shell_includes_two_siblings(
        self, tmp_path: Path, platform: Path
    ) -> None:
        a = tmp_path / "a.yaml"
        _write_project(a, repos=[{
            "repo_id": "a_node", "canonical_name": "A", "visibility": "private"
        }])
        b = tmp_path / "b.yaml"
        _write_project(b, repos=[{
            "repo_id": "b_node", "canonical_name": "B", "visibility": "private"
        }])
        shell = tmp_path / "shell.yaml"
        _write_project(shell, repos=[], includes=[
            {"name": "A", "project_manifest_path": "a.yaml"},
            {"name": "B", "project_manifest_path": "b.yaml"},
        ])

        g = load_effective_graph(platform, project=shell)
        ids = {n.repo_id for n in g.list_nodes()}
        assert {"a_node", "b_node"}.issubset(ids)


class TestCrossSubprojectEdges:
    def test_subproject_can_edge_to_sibling_subproject(
        self, tmp_path: Path, platform: Path
    ) -> None:
        a = tmp_path / "a.yaml"
        _write_project(a, repos=[{
            "repo_id": "a_node", "canonical_name": "A", "visibility": "private"
        }])
        b = tmp_path / "b.yaml"
        # B references A's node via canonical name
        _write_project(b,
            repos=[{"repo_id": "b_node", "canonical_name": "B", "visibility": "private"}],
            edges=[{"from": "B", "to": "A", "type": "dispatches_to"}],
        )
        shell = tmp_path / "shell.yaml"
        # Order matters: A must be included before B so B's edge resolves
        _write_project(shell, repos=[], includes=[
            {"name": "A", "project_manifest_path": "a.yaml"},
            {"name": "B", "project_manifest_path": "b.yaml"},
        ])

        g = load_effective_graph(platform, project=shell)
        b_edges = {(e.src, e.dst, e.type.value) for e in g.edges if e.src == "b_node"}
        assert ("b_node", "a_node", "dispatches_to") in b_edges


class TestShellOwnNodes:
    def test_shell_can_declare_own_repos_alongside_includes(
        self, tmp_path: Path, platform: Path
    ) -> None:
        sub = tmp_path / "sub.yaml"
        _write_project(sub, repos=[{
            "repo_id": "sub_node", "canonical_name": "Sub", "visibility": "private"
        }])
        shell = tmp_path / "shell.yaml"
        _write_project(shell,
            repos=[{
                "repo_id": "shell_node",
                "canonical_name": "Shell",
                "visibility": "private",
            }],
            includes=[{"name": "Sub", "project_manifest_path": "sub.yaml"}],
        )

        g = load_effective_graph(platform, project=shell)
        ids = {n.repo_id for n in g.list_nodes()}
        assert {"sub_node", "shell_node"}.issubset(ids)


# ---------------------------------------------------------------------------
# Failure modes
# ---------------------------------------------------------------------------


class TestCollisions:
    def test_subproject_redefining_platform_node_rejected(
        self, tmp_path: Path, platform: Path
    ) -> None:
        sub = tmp_path / "sub.yaml"
        _write_project(sub, repos=[{
            "repo_id": "operations_center",  # collides with platform
            "canonical_name": "Imposter", "visibility": "private",
        }])
        shell = tmp_path / "shell.yaml"
        _write_project(shell, repos=[], includes=[
            {"name": "S", "project_manifest_path": "sub.yaml"}
        ])

        with pytest.raises(RepoGraphConfigError, match="cannot redefine platform"):
            load_effective_graph(platform, project=shell)

    def test_sibling_subprojects_with_same_repo_id_rejected(
        self, tmp_path: Path, platform: Path
    ) -> None:
        a = tmp_path / "a.yaml"
        _write_project(a, repos=[{
            "repo_id": "shared", "canonical_name": "FromA", "visibility": "private"
        }])
        b = tmp_path / "b.yaml"
        _write_project(b, repos=[{
            "repo_id": "shared", "canonical_name": "FromB", "visibility": "private"
        }])
        shell = tmp_path / "shell.yaml"
        _write_project(shell, repos=[], includes=[
            {"name": "A", "project_manifest_path": "a.yaml"},
            {"name": "B", "project_manifest_path": "b.yaml"},
        ])

        with pytest.raises(RepoGraphConfigError, match="already declared"):
            load_effective_graph(platform, project=shell)

    def test_shell_redefining_subproject_node_rejected(
        self, tmp_path: Path, platform: Path
    ) -> None:
        sub = tmp_path / "sub.yaml"
        _write_project(sub, repos=[{
            "repo_id": "x", "canonical_name": "X", "visibility": "private"
        }])
        shell = tmp_path / "shell.yaml"
        _write_project(shell,
            repos=[{
                "repo_id": "x",  # collides with included sub-project
                "canonical_name": "ShellX",
                "visibility": "private",
            }],
            includes=[{"name": "S", "project_manifest_path": "sub.yaml"}],
        )

        with pytest.raises(RepoGraphConfigError, match="already declared"):
            load_effective_graph(platform, project=shell)


class TestCycles:
    def test_self_include_rejected(
        self, tmp_path: Path, platform: Path
    ) -> None:
        cyclic = tmp_path / "cyclic.yaml"
        _write_project(
            cyclic,
            repos=[{"repo_id": "n", "canonical_name": "N", "visibility": "private"}],
            includes=[{"name": "self", "project_manifest_path": "cyclic.yaml"}],
        )
        with pytest.raises(RepoGraphConfigError, match="cycle detected"):
            load_effective_graph(platform, project=cyclic)

    def test_two_step_cycle_rejected(
        self, tmp_path: Path, platform: Path
    ) -> None:
        a = tmp_path / "a.yaml"
        b = tmp_path / "b.yaml"
        _write_project(
            a,
            repos=[{"repo_id": "an", "canonical_name": "AN", "visibility": "private"}],
            includes=[{"name": "B", "project_manifest_path": "b.yaml"}],
        )
        _write_project(
            b,
            repos=[{"repo_id": "bn", "canonical_name": "BN", "visibility": "private"}],
            includes=[{"name": "A", "project_manifest_path": "a.yaml"}],
        )
        with pytest.raises(RepoGraphConfigError, match="cycle detected"):
            load_effective_graph(platform, project=a)


class TestDepth:
    def test_deep_chain_within_limit(
        self, tmp_path: Path, platform: Path
    ) -> None:
        # Build a 3-deep chain: shell → mid → leaf
        leaf = tmp_path / "leaf.yaml"
        _write_project(leaf, repos=[{
            "repo_id": "leaf_n", "canonical_name": "Leaf", "visibility": "private"
        }])
        mid = tmp_path / "mid.yaml"
        _write_project(mid, repos=[{
            "repo_id": "mid_n", "canonical_name": "Mid", "visibility": "private"
        }], includes=[{"name": "leaf", "project_manifest_path": "leaf.yaml"}])
        shell = tmp_path / "shell.yaml"
        _write_project(shell, repos=[], includes=[
            {"name": "mid", "project_manifest_path": "mid.yaml"}
        ])

        g = load_effective_graph(platform, project=shell)
        ids = {n.repo_id for n in g.list_nodes()}
        assert {"leaf_n", "mid_n"}.issubset(ids)

    def test_excessive_depth_rejected(
        self, tmp_path: Path, platform: Path
    ) -> None:
        # Chain longer than max_include_depth
        prev = tmp_path / "n0.yaml"
        _write_project(prev, repos=[{
            "repo_id": "n0", "canonical_name": "N0", "visibility": "private"
        }])
        for i in range(1, 10):
            cur = tmp_path / f"n{i}.yaml"
            _write_project(cur, repos=[{
                "repo_id": f"n{i}", "canonical_name": f"N{i}", "visibility": "private"
            }], includes=[{"name": f"n{i-1}", "project_manifest_path": f"n{i-1}.yaml"}])
            prev = cur
        with pytest.raises(RepoGraphConfigError, match="depth exceeded"):
            load_effective_graph(platform, project=prev, max_include_depth=4)


# ---------------------------------------------------------------------------
# Edge rules across sub-projects
# ---------------------------------------------------------------------------


class TestEdgeRules:
    def test_subproject_cannot_add_platform_to_platform_edge(
        self, tmp_path: Path, platform: Path
    ) -> None:
        # Include with an edge between two platform nodes — still forbidden
        sub = tmp_path / "sub.yaml"
        _write_project(sub,
            repos=[{
                "repo_id": "n", "canonical_name": "N", "visibility": "private"
            }],
            edges=[{"from": "OperationsCenter", "to": "CxRP", "type": "depends_on_contracts_from"}],
        )
        shell = tmp_path / "shell.yaml"
        _write_project(shell, repos=[], includes=[
            {"name": "S", "project_manifest_path": "sub.yaml"}
        ])
        with pytest.raises(RepoGraphConfigError, match="platform-to-platform"):
            load_effective_graph(platform, project=shell)


# ---------------------------------------------------------------------------
# Schema validation — includes structure
# ---------------------------------------------------------------------------


class TestIncludeShape:
    def test_include_missing_path_rejected(
        self, tmp_path: Path, platform: Path
    ) -> None:
        shell = tmp_path / "shell.yaml"
        shell.write_text(
            'manifest_kind: project\n'
            'manifest_version: "1.0.0"\n'
            'includes:\n'
            '  - {name: NoPath}\n',  # missing project_manifest_path
            encoding="utf-8",
        )
        with pytest.raises(RepoGraphConfigError, match="project_manifest_path"):
            load_effective_graph(platform, project=shell)

    def test_includes_must_be_list(
        self, tmp_path: Path, platform: Path
    ) -> None:
        shell = tmp_path / "shell.yaml"
        shell.write_text(
            'manifest_kind: project\n'
            'manifest_version: "1.0.0"\n'
            'includes: not_a_list\n',
            encoding="utf-8",
        )
        with pytest.raises(RepoGraphConfigError, match="includes.*must be a list"):
            load_effective_graph(platform, project=shell)
