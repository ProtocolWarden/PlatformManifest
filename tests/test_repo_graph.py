# SPDX-License-Identifier: SSPL-1.0
# Copyright (C) 2026 Velascat
"""Repo Graph + manifest loader tests (v0.2)."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from platform_manifest import (
    ManifestKind,
    RepoEdge,
    RepoEdgeType,
    RepoGraph,
    RepoGraphConfigError,
    RepoNode,
    Visibility,
    default_config_path,
    load_repo_graph,
)
from platform_manifest.cli import app

_LIVE_CONFIG = default_config_path()

_PLATFORM_HEADER = (
    'manifest_kind: platform\n'
    'manifest_version: "1.0.0"\n'
)


def _platform_yaml(body: str) -> str:
    return _PLATFORM_HEADER + body


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class TestModelBuild:
    def _node(
        self,
        repo_id: str,
        canonical: str,
        legacy: tuple[str, ...] = (),
        visibility: Visibility = Visibility.PUBLIC,
    ) -> RepoNode:
        return RepoNode(
            repo_id=repo_id,
            canonical_name=canonical,
            visibility=visibility,
            legacy_names=legacy,
        )

    def test_build_indexes_canonical_and_legacy(self) -> None:
        g = RepoGraph.build(
            nodes=[self._node("oc", "OperationsCenter", ("ControlPlane",))],
            edges=[],
        )
        assert g.resolve("OperationsCenter").repo_id == "oc"
        assert g.resolve("ControlPlane").repo_id == "oc"
        assert g.resolve("controlplane").repo_id == "oc"  # case-insensitive
        assert g.resolve("nope") is None

    def test_duplicate_repo_id_rejected(self) -> None:
        with pytest.raises(RepoGraphConfigError, match="duplicate repo_id"):
            RepoGraph.build(
                nodes=[self._node("a", "A"), self._node("a", "B")],
                edges=[],
            )

    def test_alias_collision_rejected(self) -> None:
        with pytest.raises(RepoGraphConfigError, match="maps to both"):
            RepoGraph.build(
                nodes=[
                    self._node("a", "A", legacy=("Common",)),
                    self._node("b", "B", legacy=("Common",)),
                ],
                edges=[],
            )

    def test_edge_to_unknown_node_rejected(self) -> None:
        with pytest.raises(RepoGraphConfigError, match="unknown dst"):
            RepoGraph.build(
                nodes=[self._node("a", "A")],
                edges=[RepoEdge(src="a", dst="ghost", type=RepoEdgeType.DISPATCHES_TO)],
            )

    def test_visibility_default_is_public(self) -> None:
        node = RepoNode(repo_id="a", canonical_name="A")
        assert node.visibility is Visibility.PUBLIC


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------


@pytest.fixture
def small_graph() -> RepoGraph:
    return RepoGraph.build(
        nodes=[
            RepoNode(repo_id="oc", canonical_name="OperationsCenter", legacy_names=("ControlPlane",)),
            RepoNode(repo_id="sb", canonical_name="SwitchBoard"),
            RepoNode(repo_id="op", canonical_name="OperatorConsole", legacy_names=("FOB",)),
            RepoNode(repo_id="cx", canonical_name="CxRP"),
        ],
        edges=[
            RepoEdge(src="op", dst="oc", type=RepoEdgeType.DISPATCHES_TO),
            RepoEdge(src="oc", dst="sb", type=RepoEdgeType.ROUTES_THROUGH),
            RepoEdge(src="oc", dst="cx", type=RepoEdgeType.DEPENDS_ON_CONTRACTS_FROM),
            RepoEdge(src="sb", dst="cx", type=RepoEdgeType.DEPENDS_ON_CONTRACTS_FROM),
        ],
    )


class TestQueries:
    def test_upstream_returns_direct_targets(self, small_graph: RepoGraph) -> None:
        names = [n.canonical_name for n in small_graph.upstream("oc")]
        assert names == ["CxRP", "SwitchBoard"]

    def test_downstream_returns_direct_sources(self, small_graph: RepoGraph) -> None:
        names = [n.canonical_name for n in small_graph.downstream("oc")]
        assert names == ["OperatorConsole"]

    def test_upstream_unknown_repo_raises(self, small_graph: RepoGraph) -> None:
        with pytest.raises(KeyError):
            small_graph.upstream("ghost")

    def test_affected_by_contract_change(self, small_graph: RepoGraph) -> None:
        consumers = [n.canonical_name for n in small_graph.affected_by_contract_change("cx")]
        assert consumers == ["OperationsCenter", "SwitchBoard"]

    def test_affected_excludes_non_contract_edges(self, small_graph: RepoGraph) -> None:
        # OC dispatches_to is not a contract dependency, so OC should NOT
        # appear as affected by an OperatorConsole change.
        affected = small_graph.affected_by_contract_change("op")
        assert affected == []


# ---------------------------------------------------------------------------
# Loader — v0.2 manifest header + visibility
# ---------------------------------------------------------------------------


class TestLoader:
    def test_load_minimal(self, tmp_path: Path) -> None:
        cfg = tmp_path / "g.yaml"
        cfg.write_text(
            _platform_yaml(
                "repos:\n"
                "  oc: {canonical_name: OperationsCenter, visibility: public,"
                " legacy_names: [ControlPlane]}\n"
                "  cx: {canonical_name: CxRP, visibility: public}\n"
                "edges:\n"
                "  - {from: OperationsCenter, to: CxRP, type: depends_on_contracts_from}\n"
            ),
            encoding="utf-8",
        )
        g = load_repo_graph(cfg)
        assert {n.repo_id for n in g.list_nodes()} == {"oc", "cx"}
        assert g.affected_by_contract_change("cx")[0].canonical_name == "OperationsCenter"

    def test_load_unknown_edge_type_rejected(self, tmp_path: Path) -> None:
        cfg = tmp_path / "g.yaml"
        cfg.write_text(
            _platform_yaml(
                "repos:\n"
                "  a: {canonical_name: A, visibility: public}\n"
                "  b: {canonical_name: B, visibility: public}\n"
                "edges:\n"
                "  - {from: A, to: B, type: bogus_edge}\n"
            ),
            encoding="utf-8",
        )
        with pytest.raises(RepoGraphConfigError, match="unknown type"):
            load_repo_graph(cfg)

    def test_load_missing_canonical_rejected(self, tmp_path: Path) -> None:
        cfg = tmp_path / "g.yaml"
        cfg.write_text(
            _platform_yaml(
                "repos:\n  bad: {visibility: public, legacy_names: [X]}\n"
            ),
            encoding="utf-8",
        )
        with pytest.raises(RepoGraphConfigError, match="canonical_name"):
            load_repo_graph(cfg)

    def test_load_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(RepoGraphConfigError, match="not found"):
            load_repo_graph(tmp_path / "nope.yaml")

    def test_missing_manifest_kind_rejected(self, tmp_path: Path) -> None:
        cfg = tmp_path / "g.yaml"
        cfg.write_text(
            'manifest_version: "1.0.0"\n'
            "repos:\n  a: {canonical_name: A, visibility: public}\n",
            encoding="utf-8",
        )
        with pytest.raises(RepoGraphConfigError, match="manifest_kind"):
            load_repo_graph(cfg)

    def test_missing_manifest_version_rejected(self, tmp_path: Path) -> None:
        cfg = tmp_path / "g.yaml"
        cfg.write_text(
            "manifest_kind: platform\n"
            "repos:\n  a: {canonical_name: A, visibility: public}\n",
            encoding="utf-8",
        )
        with pytest.raises(RepoGraphConfigError, match="manifest_version"):
            load_repo_graph(cfg)

    def test_wrong_slot_kind_rejected(self, tmp_path: Path) -> None:
        cfg = tmp_path / "g.yaml"
        cfg.write_text(
            'manifest_kind: project\n'
            'manifest_version: "1.0.0"\n'
            "repos:\n  a: {canonical_name: A, visibility: public}\n",
            encoding="utf-8",
        )
        with pytest.raises(RepoGraphConfigError, match="expected manifest_kind='platform'"):
            load_repo_graph(cfg)

    def test_unknown_kind_rejected(self, tmp_path: Path) -> None:
        cfg = tmp_path / "g.yaml"
        cfg.write_text(
            'manifest_kind: bogus\n'
            'manifest_version: "1.0.0"\n'
            "repos:\n  a: {canonical_name: A, visibility: public}\n",
            encoding="utf-8",
        )
        with pytest.raises(RepoGraphConfigError, match="unknown manifest_kind"):
            load_repo_graph(cfg)


# ---------------------------------------------------------------------------
# Visibility enforcement
# ---------------------------------------------------------------------------


class TestVisibility:
    def test_node_missing_visibility_rejected(self, tmp_path: Path) -> None:
        cfg = tmp_path / "g.yaml"
        cfg.write_text(
            _platform_yaml("repos:\n  a: {canonical_name: A}\n"),
            encoding="utf-8",
        )
        with pytest.raises(RepoGraphConfigError, match="visibility"):
            load_repo_graph(cfg)

    def test_unknown_visibility_rejected(self, tmp_path: Path) -> None:
        cfg = tmp_path / "g.yaml"
        cfg.write_text(
            _platform_yaml(
                "repos:\n  a: {canonical_name: A, visibility: classified}\n"
            ),
            encoding="utf-8",
        )
        with pytest.raises(RepoGraphConfigError, match="unknown visibility"):
            load_repo_graph(cfg)

    def test_platform_rejects_private_node(self, tmp_path: Path) -> None:
        cfg = tmp_path / "g.yaml"
        cfg.write_text(
            _platform_yaml(
                "repos:\n"
                "  oc: {canonical_name: OperationsCenter, visibility: public}\n"
                "  vf: {canonical_name: VideoFoundryAPI, visibility: private}\n"
            ),
            encoding="utf-8",
        )
        with pytest.raises(RepoGraphConfigError, match="public nodes"):
            load_repo_graph(cfg)


# ---------------------------------------------------------------------------
# Live (bundled) manifest
# ---------------------------------------------------------------------------


class TestLiveConfig:
    """The bundled platform_manifest.yaml must load cleanly and resolve the
    canonical legacy aliases the rest of the platform relies on."""

    def test_default_config_path_exists(self) -> None:
        assert _LIVE_CONFIG.exists(), _LIVE_CONFIG

    def test_live_loads(self) -> None:
        graph = load_repo_graph(_LIVE_CONFIG)
        assert graph.resolve("OperationsCenter") is not None
        assert graph.resolve("SwitchBoard") is not None

    def test_live_all_nodes_public(self) -> None:
        graph = load_repo_graph(_LIVE_CONFIG)
        assert all(
            n.visibility is Visibility.PUBLIC for n in graph.list_nodes()
        )

    def test_live_legacy_aliases_resolve(self) -> None:
        graph = load_repo_graph(_LIVE_CONFIG)
        assert graph.resolve("ControlPlane").canonical_name == "OperationsCenter"
        assert graph.resolve("FOB").canonical_name == "OperatorConsole"
        assert graph.resolve("ExecutionContractProtocol").canonical_name == "CxRP"

    def test_live_contract_change_in_cxrp_lists_consumers(self) -> None:
        graph = load_repo_graph(_LIVE_CONFIG)
        consumers = {n.canonical_name for n in graph.affected_by_contract_change("cxrp")}
        assert {"OperationsCenter", "SwitchBoard", "OperatorConsole"}.issubset(consumers)


# ---------------------------------------------------------------------------
# Schemas — packaged JSON schemas exist and are syntactically valid
# ---------------------------------------------------------------------------


class TestSchemas:
    """The three JSON schemas ship in `<repo>/schemas/`. The loader doesn't
    consume them yet (it does its own validation in Python); they exist
    for downstream tooling and as the published contract."""

    def _schemas_dir(self) -> Path:
        # Walk up from this test file: tests/ → repo root → schemas/
        return Path(__file__).resolve().parents[1] / "schemas"

    def test_three_schemas_present(self) -> None:
        d = self._schemas_dir()
        for name in (
            "platform_manifest.schema.json",
            "project_manifest.schema.json",
            "local_manifest.schema.json",
        ):
            assert (d / name).exists(), f"missing schema: {name}"

    def test_schemas_are_valid_json(self) -> None:
        import json

        d = self._schemas_dir()
        for name in (
            "platform_manifest.schema.json",
            "project_manifest.schema.json",
            "local_manifest.schema.json",
        ):
            payload = json.loads((d / name).read_text(encoding="utf-8"))
            assert payload.get("$schema", "").startswith("https://json-schema.org/")
            assert "title" in payload


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


class TestCLI:
    def setup_method(self) -> None:
        self.runner = CliRunner()

    def test_list(self) -> None:
        result = self.runner.invoke(app, ["list"])
        assert result.exit_code == 0, result.output
        assert "OperationsCenter" in result.output

    def test_resolve_legacy(self) -> None:
        result = self.runner.invoke(app, ["resolve", "ControlPlane"])
        assert result.exit_code == 0, result.output
        assert "OperationsCenter" in result.output

    def test_resolve_unknown_exits_nonzero(self) -> None:
        result = self.runner.invoke(app, ["resolve", "Nope"])
        assert result.exit_code != 0

    def test_impact_lists_consumers(self) -> None:
        result = self.runner.invoke(app, ["impact", "cxrp"])
        assert result.exit_code == 0, result.output
        assert "OperationsCenter" in result.output
        assert "SwitchBoard" in result.output


# ---------------------------------------------------------------------------
# ManifestKind enum smoke
# ---------------------------------------------------------------------------


class TestManifestKind:
    def test_values_match_design_doc(self) -> None:
        assert ManifestKind.PLATFORM.value == "platform"
        assert ManifestKind.PROJECT.value == "project"
        assert ManifestKind.LOCAL.value == "local"
