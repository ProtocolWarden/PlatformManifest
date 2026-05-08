# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Velascat
"""Tests for platform_manifest.validate + the `validate` CLI subcommand."""
from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from platform_manifest import ManifestKind
from platform_manifest.cli import app
from platform_manifest.validate import validate_manifest


# ---------------------------------------------------------------------------
# Fixtures — minimal valid manifests for each kind
# ---------------------------------------------------------------------------


_PLATFORM_VALID = """\
manifest_kind: platform
manifest_version: "1.0.0"
repos:
  oc:
    canonical_name: OperationsCenter
    visibility: public
edges: []
"""

_PROJECT_VALID = """\
manifest_kind: project
manifest_version: "1.0.0"
platform_manifest:
  name: PlatformManifest
  version_constraint: ">=0.3,<1.0"
repos:
  vfa:
    canonical_name: VFAApi
    visibility: private
edges: []
"""

_LOCAL_VALID = """\
manifest_kind: local
manifest_version: "1.0.0"
repos:
  oc:
    local_path: /opt/oc
    local_port: 8080
"""


def _write(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Happy paths — each kind validates clean
# ---------------------------------------------------------------------------


class TestValidManifests:
    def test_valid_platform(self, tmp_path: Path) -> None:
        report = validate_manifest(_write(tmp_path, "p.yaml", _PLATFORM_VALID))
        assert report.ok, [i.message for i in report.issues]
        assert report.detected_kind is ManifestKind.PLATFORM

    def test_valid_project(self, tmp_path: Path) -> None:
        report = validate_manifest(_write(tmp_path, "p.yaml", _PROJECT_VALID))
        assert report.ok, [i.message for i in report.issues]
        assert report.detected_kind is ManifestKind.PROJECT

    def test_valid_local(self, tmp_path: Path) -> None:
        report = validate_manifest(_write(tmp_path, "p.yaml", _LOCAL_VALID))
        assert report.ok, [i.message for i in report.issues]
        assert report.detected_kind is ManifestKind.LOCAL


# ---------------------------------------------------------------------------
# Bundled platform_manifest.yaml validates clean against its own schema
# ---------------------------------------------------------------------------


class TestBundledPlatformManifest:
    def test_bundled_validates_clean(self) -> None:
        from platform_manifest import default_config_path

        report = validate_manifest(default_config_path())
        assert report.ok, [i.to_dict() for i in report.issues]
        assert report.detected_kind is ManifestKind.PLATFORM


# ---------------------------------------------------------------------------
# Schema failures
# ---------------------------------------------------------------------------


class TestSchemaFailures:
    def test_missing_manifest_kind(self, tmp_path: Path) -> None:
        report = validate_manifest(
            _write(tmp_path, "p.yaml", 'manifest_version: "1.0.0"\nrepos: {}\n')
        )
        assert not report.ok
        assert any("manifest_kind" in i.message for i in report.issues)

    def test_unknown_manifest_kind(self, tmp_path: Path) -> None:
        report = validate_manifest(
            _write(
                tmp_path, "p.yaml",
                'manifest_kind: bogus\nmanifest_version: "1.0.0"\n'
            )
        )
        assert not report.ok
        assert any("unknown manifest_kind" in i.message for i in report.issues)

    def test_platform_with_private_node_schema_rejects(self, tmp_path: Path) -> None:
        report = validate_manifest(
            _write(tmp_path, "p.yaml",
                'manifest_kind: platform\n'
                'manifest_version: "1.0.0"\n'
                'repos:\n'
                '  vfa:\n'
                '    canonical_name: VFA\n'
                '    visibility: private\n'
            )
        )
        # Schema's `visibility: const "public"` rejects private at the schema layer
        assert not report.ok
        assert any("public" in i.message.lower() or "constant" in i.message.lower() for i in report.issues)

    def test_local_with_canonical_name_rejected_by_schema(self, tmp_path: Path) -> None:
        report = validate_manifest(
            _write(tmp_path, "p.yaml",
                'manifest_kind: local\n'
                'manifest_version: "1.0.0"\n'
                'repos:\n'
                '  oc:\n'
                '    canonical_name: OperationsCenter\n'  # not in allowlist
            )
        )
        assert not report.ok
        assert any("canonical_name" in str(i.to_dict()) or "additional" in str(i.to_dict()).lower()
                   for i in report.issues)

    def test_io_error_for_missing_file(self, tmp_path: Path) -> None:
        report = validate_manifest(tmp_path / "does_not_exist.yaml")
        assert not report.ok
        assert any(i.severity == "io" for i in report.issues)

    def test_yaml_parse_error(self, tmp_path: Path) -> None:
        report = validate_manifest(
            _write(tmp_path, "p.yaml", "manifest_kind: platform\n  bad: indent: here\n")
        )
        assert not report.ok
        assert any("YAML" in i.message for i in report.issues)


# ---------------------------------------------------------------------------
# Loader-stage failures (semantic issues schema can't catch)
# ---------------------------------------------------------------------------


class TestLoaderStage:
    def test_duplicate_repo_id_caught_by_loader(self, tmp_path: Path) -> None:
        # Schema can't catch alias collisions across nodes — the loader does
        report = validate_manifest(
            _write(tmp_path, "p.yaml",
                'manifest_kind: platform\n'
                'manifest_version: "1.0.0"\n'
                'repos:\n'
                '  a: {canonical_name: Same, visibility: public, legacy_names: [Common]}\n'
                '  b: {canonical_name: Other, visibility: public, legacy_names: [Common]}\n'
            )
        )
        assert not report.ok
        assert any(i.severity == "loader" and "maps to both" in i.message for i in report.issues)


# ---------------------------------------------------------------------------
# Slot enforcement
# ---------------------------------------------------------------------------


class TestSlotEnforcement:
    def test_expected_match_passes(self, tmp_path: Path) -> None:
        report = validate_manifest(
            _write(tmp_path, "p.yaml", _PROJECT_VALID),
            expected=ManifestKind.PROJECT,
        )
        assert report.ok

    def test_expected_mismatch_fails_with_clear_message(self, tmp_path: Path) -> None:
        report = validate_manifest(
            _write(tmp_path, "p.yaml", _PROJECT_VALID),
            expected=ManifestKind.PLATFORM,
        )
        assert not report.ok
        assert any("does not match" in i.message for i in report.issues)
        # detected_kind is still set so callers can report the actual file shape
        assert report.detected_kind is ManifestKind.PROJECT


# ---------------------------------------------------------------------------
# CLI surface
# ---------------------------------------------------------------------------


class TestCLI:
    def setup_method(self) -> None:
        self.runner = CliRunner()

    def test_clean_manifest_exit_zero(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "p.yaml", _PLATFORM_VALID)
        result = self.runner.invoke(app, ["validate", str(p)])
        assert result.exit_code == 0, result.output
        assert "clean" in result.output

    def test_dirty_manifest_exit_one(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "p.yaml", "manifest_kind: bogus\nmanifest_version: '1.0.0'\n")
        result = self.runner.invoke(app, ["validate", str(p)])
        assert result.exit_code == 1
        assert "issue" in result.output.lower() or "✗" in result.output

    def test_expected_flag_enforces_slot(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "p.yaml", _PROJECT_VALID)
        result = self.runner.invoke(app, ["validate", str(p), "--expected", "platform"])
        assert result.exit_code == 1
        assert "does not match" in result.output.lower()

    def test_invalid_expected_flag_exits_two(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "p.yaml", _PLATFORM_VALID)
        result = self.runner.invoke(app, ["validate", str(p), "--expected", "bogus"])
        assert result.exit_code == 2
        assert "must be one of" in result.output.lower()

    def test_json_output_emits_valid_json(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "p.yaml", _PLATFORM_VALID)
        result = self.runner.invoke(app, ["validate", str(p), "--json"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["ok"] is True
        assert payload["detected_kind"] == "platform"
        assert payload["issues"] == []

    def test_json_output_includes_issues_on_failure(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "p.yaml", "manifest_kind: bogus\n")
        result = self.runner.invoke(app, ["validate", str(p), "--json"])
        assert result.exit_code == 1
        payload = json.loads(result.output)
        assert payload["ok"] is False
        assert len(payload["issues"]) >= 1
        assert payload["issues"][0]["severity"] in {"schema", "loader", "io"}
