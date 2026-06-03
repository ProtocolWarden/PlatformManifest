# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 ProtocolWarden
"""Tests for the public projection CLI."""

from __future__ import annotations

import json
import re
from pathlib import Path

from typer.testing import CliRunner

from platform_manifest.cli import app
from platform_manifest.validate import ValidationIssue, ValidationReport

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _strip_ansi(text: str) -> str:
    """Drop ANSI style codes so substring checks survive forced color.

    Rich styles error text (e.g. in CI where FORCE_COLOR is set), interleaving
    escape codes inside option names — so a raw `"--opt" in output` check fails
    even though the user sees the option. Strip the codes before asserting.
    """
    return _ANSI_RE.sub("", text)


_PLATFORM_YAML = """\
manifest_kind: platform
manifest_version: "1.0.0"
repos:
  operations_center:
    canonical_name: OperationsCenter
    visibility: public
edges: []
"""


_PROJECT_YAML = """\
manifest_kind: project
manifest_version: "1.0.0"
repos:
  private_impl:
    canonical_name: PrivateImpl
    visibility: private
    github_url: https://github.com/private/private-impl
  public_docs:
    canonical_name: PublicDocs
    visibility: public
    kind: PublicRepository
edges:
  - {from: PrivateImpl, to: OperationsCenter, type: dispatches_to}
  - {from: PublicDocs, to: OperationsCenter, type: depends_on_contracts_from}
"""


_LOCAL_YAML = """\
manifest_kind: local
manifest_version: "1.0.0"
repos:
  operations_center:
    local_path: /home/dev/private/OperationsCenter
    env_file: /home/dev/private/.env
"""


def _write(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


class TestProjectPublicCLI:
    def setup_method(self) -> None:
        self.runner = CliRunner()

    def test_emits_public_projection_json(self, tmp_path: Path) -> None:
        result = self.runner.invoke(
            app,
            [
                "project-public",
                "--base",
                str(_write(tmp_path, "platform.yaml", _PLATFORM_YAML)),
                "--project",
                str(_write(tmp_path, "project.yaml", _PROJECT_YAML)),
                "--local",
                str(_write(tmp_path, "local.yaml", _LOCAL_YAML)),
            ],
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        rendered = json.dumps(payload, sort_keys=True)
        assert payload["manifest_kind"] == "platform"
        assert set(payload["repos"]) == {"operations_center", "public_docs"}
        assert payload["repos"]["public_docs"]["kind"] == "PublicRepository"
        assert "PrivateImpl" not in rendered
        assert "github.com/private" not in rendered
        assert "/home/dev/private" not in rendered
        assert all(
            edge["from"] in payload["repos"] and edge["to"] in payload["repos"]
            for edge in payload["edges"]
        )

    def test_writes_output_file(self, tmp_path: Path) -> None:
        out = tmp_path / "public_manifest.json"
        result = self.runner.invoke(
            app,
            [
                "project-public",
                "--base",
                str(_write(tmp_path, "platform.yaml", _PLATFORM_YAML)),
                "--project",
                str(_write(tmp_path, "project.yaml", _PROJECT_YAML)),
                "--output",
                str(out),
            ],
        )

        assert result.exit_code == 0, result.output
        assert json.loads(out.read_text(encoding="utf-8"))["manifest_kind"] == "platform"
        assert result.output == ""

    def test_composition_error_exits_two(self, tmp_path: Path) -> None:
        bad_project = _write(
            tmp_path,
            "bad_project.yaml",
            'manifest_kind: project\n'
            'manifest_version: "1.0.0"\n'
            'repos:\n'
            '  operations_center:\n'
            '    canonical_name: Impostor\n'
            '    visibility: private\n',
        )
        result = self.runner.invoke(
            app,
            [
                "project-public",
                "--base",
                str(_write(tmp_path, "platform.yaml", _PLATFORM_YAML)),
                "--project",
                str(bad_project),
            ],
        )

        assert result.exit_code == 2
        assert "composition error" in result.output.lower()

    def test_no_validate_is_not_allowed_on_safe_command(self, tmp_path: Path) -> None:
        result = self.runner.invoke(
            app,
            [
                "project-public",
                "--base",
                str(_write(tmp_path, "platform.yaml", _PLATFORM_YAML)),
                "--project",
                str(_write(tmp_path, "project.yaml", _PROJECT_YAML)),
                "--no-validate",
            ],
        )

        assert result.exit_code != 0
        assert "--no-validate" in _strip_ansi(result.output)

    def test_unsafe_command_emits_warning(self, tmp_path: Path) -> None:
        result = self.runner.invoke(
            app,
            [
                "project-public-unsafe",
                "--base",
                str(_write(tmp_path, "platform.yaml", _PLATFORM_YAML)),
                "--project",
                str(_write(tmp_path, "project.yaml", _PROJECT_YAML)),
            ],
        )

        assert result.exit_code == 0, result.output
        assert "warning" in result.output.lower()

    def test_safe_command_does_not_write_output_on_validation_failure(
        self,
        tmp_path: Path,
        monkeypatch,
    ) -> None:
        out = tmp_path / "public_manifest.json"

        def _fail_validate(*args, **kwargs):
            return ValidationReport(
                path=Path("synthetic.json"),
                detected_kind=None,
                issues=(ValidationIssue(severity="schema", message="boom"),),
            )

        monkeypatch.setattr("platform_manifest.cli.validate_manifest", _fail_validate)

        result = self.runner.invoke(
            app,
            [
                "project-public",
                "--base",
                str(_write(tmp_path, "platform.yaml", _PLATFORM_YAML)),
                "--project",
                str(_write(tmp_path, "project.yaml", _PROJECT_YAML)),
                "--output",
                str(out),
            ],
        )

        assert result.exit_code == 1
        assert not out.exists()

    def test_safe_command_does_not_clobber_existing_output_on_validation_failure(
        self,
        tmp_path: Path,
        monkeypatch,
    ) -> None:
        out = tmp_path / "public_manifest.json"
        out.write_text('{"preserve": true}\n', encoding="utf-8")
        original = out.read_text(encoding="utf-8")

        def _fail_validate(*args, **kwargs):
            return ValidationReport(
                path=Path("synthetic.json"),
                detected_kind=None,
                issues=(ValidationIssue(severity="schema", message="boom"),),
            )

        monkeypatch.setattr("platform_manifest.cli.validate_manifest", _fail_validate)

        result = self.runner.invoke(
            app,
            [
                "project-public",
                "--base",
                str(_write(tmp_path, "platform.yaml", _PLATFORM_YAML)),
                "--project",
                str(_write(tmp_path, "project.yaml", _PROJECT_YAML)),
                "--output",
                str(out),
            ],
        )

        assert result.exit_code == 1
        assert out.read_text(encoding="utf-8") == original
