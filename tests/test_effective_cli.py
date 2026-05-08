# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Velascat
"""Tests for the `platform-manifest effective` CLI subcommand (v0.5)."""
from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from platform_manifest.cli import app


_PROJECT_YAML = """\
manifest_kind: project
manifest_version: "1.0.0"
repos:
  myproj:
    canonical_name: MyProj
    visibility: private
edges:
  - {from: MyProj, to: OperationsCenter, type: dispatches_to}
"""

_LOCAL_YAML = """\
manifest_kind: local
manifest_version: "1.0.0"
repos:
  operations_center:
    local_path: /opt/oc
    local_port: 8080
"""


class TestEffectiveCLI:
    def setup_method(self) -> None:
        self.runner = CliRunner()

    def test_platform_only_lists_public_nodes(self) -> None:
        # Use --json to avoid Rich's terminal-width truncation in CI test mode.
        result = self.runner.invoke(app, ["effective", "--json"])
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        names = {n["canonical_name"] for n in payload["nodes"]}
        assert "OperationsCenter" in names
        assert all(n["source"] == "platform" for n in payload["nodes"])

    def test_with_project_shows_private_node(self, tmp_path: Path) -> None:
        proj = tmp_path / "p.yaml"
        proj.write_text(_PROJECT_YAML, encoding="utf-8")
        result = self.runner.invoke(
            app, ["effective", "--project", str(proj), "--json"]
        )
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        myproj = next((n for n in payload["nodes"] if n["repo_id"] == "myproj"), None)
        assert myproj is not None
        assert myproj["source"] == "project"
        assert myproj["visibility"] == "private"
        # Edge from project surfaces with provenance
        proj_edges = [e for e in payload["edges"] if e["source"] == "project"]
        assert any(e["from"] == "myproj" and e["type"] == "dispatches_to" for e in proj_edges)

    def test_with_local_shows_annotations(self, tmp_path: Path) -> None:
        local = tmp_path / "l.yaml"
        local.write_text(_LOCAL_YAML, encoding="utf-8")
        result = self.runner.invoke(app, ["effective", "--local", str(local), "--json"])
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        oc = next((n for n in payload["nodes"] if n["repo_id"] == "operations_center"), None)
        assert oc is not None
        assert oc["local_path"] == "/opt/oc"
        assert oc["local_port"] == 8080

    def test_full_three_layer_composition(self, tmp_path: Path) -> None:
        proj = tmp_path / "p.yaml"
        proj.write_text(_PROJECT_YAML, encoding="utf-8")
        local = tmp_path / "l.yaml"
        local.write_text(_LOCAL_YAML, encoding="utf-8")
        result = self.runner.invoke(
            app,
            ["effective", "--project", str(proj), "--local", str(local), "--json"],
        )
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        names = {n["canonical_name"] for n in payload["nodes"]}
        assert "MyProj" in names
        oc = next((n for n in payload["nodes"] if n["repo_id"] == "operations_center"), None)
        assert oc is not None and oc["local_path"] == "/opt/oc"

    def test_json_output_is_valid(self, tmp_path: Path) -> None:
        proj = tmp_path / "p.yaml"
        proj.write_text(_PROJECT_YAML, encoding="utf-8")
        result = self.runner.invoke(app, ["effective", "--project", str(proj), "--json"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert "nodes" in payload
        assert "edges" in payload
        # MyProj is in nodes with source=project
        myproj = next((n for n in payload["nodes"] if n["repo_id"] == "myproj"), None)
        assert myproj is not None
        assert myproj["source"] == "project"
        assert myproj["visibility"] == "private"

    def test_composition_error_exits_two(self, tmp_path: Path) -> None:
        # Project tries to redefine a platform repo_id
        proj = tmp_path / "bad.yaml"
        proj.write_text(
            'manifest_kind: project\n'
            'manifest_version: "1.0.0"\n'
            'repos:\n'
            '  operations_center:\n'
            '    canonical_name: ImpostorOC\n'
            '    visibility: private\n',
            encoding="utf-8",
        )
        result = self.runner.invoke(app, ["effective", "--project", str(proj)])
        assert result.exit_code == 2
        assert "composition error" in result.output.lower()

    def test_custom_base_override(self, tmp_path: Path) -> None:
        # Build a tiny custom platform base + verify it's the one used
        custom = tmp_path / "platform.yaml"
        custom.write_text(
            'manifest_kind: platform\n'
            'manifest_version: "1.0.0"\n'
            'repos:\n'
            '  only_one:\n'
            '    canonical_name: OnlyOne\n'
            '    visibility: public\n',
            encoding="utf-8",
        )
        result = self.runner.invoke(app, ["effective", "--base", str(custom), "--json"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        names = {n["canonical_name"] for n in payload["nodes"]}
        assert names == {"OnlyOne"}
