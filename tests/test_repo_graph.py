# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 ProtocolWarden
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
        public_label: str | None = None,
        visibility: Visibility = Visibility.PUBLIC,
    ) -> RepoNode:
        return RepoNode(
            repo_id=repo_id,
            canonical_name=canonical,
            visibility=visibility,
            public_alias=public_label,
        )

    def test_build_indexes_canonical_only(self) -> None:
        g = RepoGraph.build(
            nodes=[self._node("oc", "OperationsCenter")],
            edges=[],
        )
        assert g.resolve("OperationsCenter").repo_id == "oc"
        assert g.resolve("operationscenter").repo_id == "oc"  # case-insensitive
        assert g.resolve("nope") is None

    def test_duplicate_repo_id_rejected(self) -> None:
        with pytest.raises(RepoGraphConfigError, match="duplicate repo_id"):
            RepoGraph.build(
                nodes=[self._node("a", "A"), self._node("a", "B")],
                edges=[],
            )

    def test_label_collision_rejected(self) -> None:
        with pytest.raises(RepoGraphConfigError, match="maps to both"):
            RepoGraph.build(
                nodes=[
                    self._node("a", "A", public_label="Common"),
                    self._node("b", "B", public_label="Common"),
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
        assert node.kind == "Repository"


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------


@pytest.fixture
def small_graph() -> RepoGraph:
    return RepoGraph.build(
        nodes=[
            RepoNode(repo_id="oc", canonical_name="OperationsCenter"),
            RepoNode(repo_id="sb", canonical_name="SwitchBoard"),
            RepoNode(repo_id="op", canonical_name="OperatorConsole"),
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

    def test_who_dispatches_to_returns_dispatch_sources(
        self, small_graph: RepoGraph
    ) -> None:
        # OperatorConsole dispatches_to OperationsCenter — so OC's
        # dispatchers include OperatorConsole.
        names = [n.canonical_name for n in small_graph.who_dispatches_to("oc")]
        assert names == ["OperatorConsole"]

    def test_who_dispatches_to_excludes_non_dispatch_edges(
        self, small_graph: RepoGraph
    ) -> None:
        # CxRP only has depends_on_contracts_from edges into it (no dispatches),
        # so who_dispatches_to should be empty.
        assert small_graph.who_dispatches_to("cx") == []

    def test_who_dispatches_to_unknown_repo_raises(
        self, small_graph: RepoGraph
    ) -> None:
        with pytest.raises(KeyError):
            small_graph.who_dispatches_to("ghost")

    def test_who_consumes_assets_of_on_synthetic_graph(self) -> None:
        # Build a tiny graph with BUNDLES_ASSETS_FROM edges. Synthetic
        # node names — the algorithm under test is repo-name-agnostic.
        graph = RepoGraph.build(
            nodes=[
                RepoNode(repo_id="api", canonical_name="GenericApi"),
                RepoNode(repo_id="worker", canonical_name="GenericWorker"),
                RepoNode(repo_id="publisher", canonical_name="AssetPublisher"),
            ],
            edges=[
                RepoEdge(src="api", dst="publisher", type=RepoEdgeType.BUNDLES_ASSETS_FROM),
                RepoEdge(src="worker", dst="publisher", type=RepoEdgeType.BUNDLES_ASSETS_FROM),
            ],
        )
        consumers = [n.canonical_name for n in graph.who_consumes_assets_of("publisher")]
        assert consumers == ["GenericApi", "GenericWorker"]

    def test_who_consumes_assets_of_excludes_other_edges(self) -> None:
        graph = RepoGraph.build(
            nodes=[
                RepoNode(repo_id="a", canonical_name="A"),
                RepoNode(repo_id="b", canonical_name="B"),
            ],
            edges=[
                RepoEdge(src="a", dst="b", type=RepoEdgeType.DEPENDS_ON_CONTRACTS_FROM),
            ],
        )
        # B is the contract owner, not the asset producer — empty
        assert graph.who_consumes_assets_of("b") == []

    def test_who_consumes_assets_of_unknown_repo_raises(self) -> None:
        graph = RepoGraph.build(
            nodes=[RepoNode(repo_id="a", canonical_name="A")],
            edges=[],
        )
        with pytest.raises(KeyError):
            graph.who_consumes_assets_of("ghost")

    def test_who_dispatches_to_on_live_graph(self) -> None:
        # The bundled platform manifest has OperatorConsole -> OperationsCenter
        # as its only dispatches_to into operations_center; the reverse
        # direction (OperationsCenter -> CoreRunner / SourceRegistry)
        # is what dispatches OUT of OC.
        graph = load_repo_graph(_LIVE_CONFIG)
        oc_dispatchers = {n.canonical_name for n in graph.who_dispatches_to("operations_center")}
        assert "OperatorConsole" in oc_dispatchers
        # CoreRunner is dispatched-TO by OC, so OC should appear as a
        # dispatcher of CoreRunner.
        er_dispatchers = {n.canonical_name for n in graph.who_dispatches_to("core_runner")}
        assert "OperationsCenter" in er_dispatchers


# ---------------------------------------------------------------------------
# Loader — v0.2 manifest header + visibility
# ---------------------------------------------------------------------------


class TestLoader:
    def test_load_minimal(self, tmp_path: Path) -> None:
        cfg = tmp_path / "g.yaml"
        cfg.write_text(
            _platform_yaml(
                "repos:\n"
                "  oc: {canonical_name: OperationsCenter, visibility: public}\n"
                "  cx: {canonical_name: CxRP, visibility: public}\n"
                "edges:\n"
                "  - {from: OperationsCenter, to: CxRP, type: depends_on_contracts_from}\n"
            ),
            encoding="utf-8",
        )
        g = load_repo_graph(cfg)
        assert {n.repo_id for n in g.list_nodes()} == {"oc", "cx"}
        assert g.affected_by_contract_change("cx")[0].canonical_name == "OperationsCenter"

    def test_loads_optional_ontology_fields(self, tmp_path: Path) -> None:
        cfg = tmp_path / "g.yaml"
        cfg.write_text(
            _platform_yaml(
                "repos:\n"
                "  oc:\n"
                "    canonical_name: OperationsCenter\n"
                "    visibility: public\n"
                "    kind: Repository\n"
                "    owner: ProtocolWarden\n"
                "    scope: platform\n"
                "    metadata:\n"
                "      documentation_url: https://github.com/ProtocolWarden/OperationsCenter\n"
                "      public_contract_surface: true\n"
                "edges: []\n"
            ),
            encoding="utf-8",
        )
        graph = load_repo_graph(cfg)
        node = graph.resolve("OperationsCenter")
        assert node is not None
        assert node.kind == "Repository"
        assert node.owner == "ProtocolWarden"
        assert node.scope == "platform"
        assert dict(node.metadata) == {
            "documentation_url": "https://github.com/ProtocolWarden/OperationsCenter",
            "public_contract_surface": True,
        }

    def test_metadata_rejects_nested_contract_schema_copy(self, tmp_path: Path) -> None:
        cfg = tmp_path / "g.yaml"
        cfg.write_text(
            _platform_yaml(
                "repos:\n"
                "  cx:\n"
                "    canonical_name: CxRP\n"
                "    visibility: public\n"
                "    metadata:\n"
                "      copied_schema:\n"
                "        ExecutionRequest: {}\n"
            ),
            encoding="utf-8",
        )
        with pytest.raises(RepoGraphConfigError, match="metadata\\[copied_schema\\]"):
            load_repo_graph(cfg)

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
                "repos:\n  bad: {visibility: public, public_alias: X}\n"
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
                "  ga: {canonical_name: GenericRepoA, visibility: private}\n"
            ),
            encoding="utf-8",
        )
        with pytest.raises(RepoGraphConfigError, match="public nodes"):
            load_repo_graph(cfg)

    def test_load_rejects_invalid_visibility_scope(self, tmp_path: Path) -> None:
        # The loader fail-closes on an invalid visibility_scope even when every
        # repo is public (so the platform public-only check passes) — this is the
        # parse_visibility_scope wire enforcing docs/inject/loader.md.
        cfg = tmp_path / "g.yaml"
        cfg.write_text(
            _platform_yaml(
                "visibility_scope: bogus\n"
                "repos:\n"
                "  oc: {canonical_name: OperationsCenter, visibility: public}\n"
            ),
            encoding="utf-8",
        )
        with pytest.raises(RepoGraphConfigError, match="visibility_scope must be"):
            load_repo_graph(cfg)


# ---------------------------------------------------------------------------
# Live (bundled) manifest
# ---------------------------------------------------------------------------


class TestLiveConfig:
    """The bundled platform_manifest.yaml must load cleanly and resolve
    canonical repo names only."""

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

    def test_live_canonical_names_resolve(self) -> None:
        graph = load_repo_graph(_LIVE_CONFIG)
        assert graph.resolve("OperationsCenter").canonical_name == "OperationsCenter"
        assert graph.resolve("OperatorConsole").canonical_name == "OperatorConsole"
        assert graph.resolve("CxRP").canonical_name == "CxRP"

    def test_live_contract_change_in_cxrp_lists_consumers(self) -> None:
        graph = load_repo_graph(_LIVE_CONFIG)
        consumers = {n.canonical_name for n in graph.affected_by_contract_change("cxrp")}
        assert {"OperationsCenter", "SwitchBoard", "OperatorConsole"}.issubset(consumers)


# ---------------------------------------------------------------------------
# Schemas — packaged JSON schemas exist and are syntactically valid
# ---------------------------------------------------------------------------


class TestSchemas:
    """The three JSON schemas ship as package data under
    ``platform_manifest.schemas`` and are resolved via
    ``importlib.resources`` so installed wheels behave the same as
    source checkouts. v0.4 added the validate CLI that reads them."""

    _NAMES = (
        "platform_manifest.schema.json",
        "project_manifest.schema.json",
        "local_manifest.schema.json",
    )

    def test_three_schemas_present(self) -> None:
        from importlib import resources

        for name in self._NAMES:
            assert (resources.files("platform_manifest.schemas") / name).is_file(), (
                f"missing schema: {name}"
            )

    def test_schemas_are_valid_json(self) -> None:
        import json
        from importlib import resources

        for name in self._NAMES:
            raw = (resources.files("platform_manifest.schemas") / name).read_text(
                encoding="utf-8"
            )
            payload = json.loads(raw)
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

    def test_resolve_canonical(self) -> None:
        result = self.runner.invoke(app, ["resolve", "OperationsCenter"])
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
