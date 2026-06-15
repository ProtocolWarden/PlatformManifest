# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 ProtocolWarden
"""Tests for the platform capability registry read-model + CLI."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from platform_manifest.capabilities import (
    default_capabilities_path,
    load_capabilities,
    load_default_capabilities,
    platform_repo_ids,
)
from platform_manifest import capabilities_cli
from platform_manifest.cli import app
from platform_manifest.errors import RepoGraphConfigError

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


_SEEDED = {"repo_health_audit", "board_unblock", "session_gc"}

_VALID_DOC = """\
schema_kind: capabilities
schema_version: 1.0.0
capabilities:
  - action_id: demo_audit
    name: Demo Audit
    owner_repo_id: custodian
    target_scope:
      kind: repo
      repo_id: operations_center
    executes_on: custodian
    category: audit
    risk: read_only
    invocation:
      kind: cli
      ref: demo
"""


def _write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "capabilities.yaml"
    path.write_text(body, encoding="utf-8")
    return path


# ── registry load ───────────────────────────────────────────────────────────────


def test_default_registry_has_seeded_capabilities() -> None:
    registry = load_default_capabilities()
    assert {n.action_id for n in registry.list_capabilities()} == _SEEDED


def test_seed_owners_resolve_to_real_repos() -> None:
    registry = load_default_capabilities()
    owners = {n.action_id: registry.owner_of(n.action_id) for n in registry.list_capabilities()}
    repo_ids = platform_repo_ids()
    assert owners["repo_health_audit"] == "custodian"
    assert owners["board_unblock"] == "operations_center"
    assert owners["session_gc"] == "context_lifecycle_protocol"
    assert set(owners.values()) <= repo_ids


def test_fleet_mutating_seeds_declare_a_lane() -> None:
    # risk >= mutates_fleet must carry an explicit preferred_lane (RepoGraph invariant).
    registry = load_default_capabilities()
    for node in registry.list_capabilities():
        if node.risk.value in {"mutates_fleet", "irreversible"}:
            assert node.preferred_lane, f"{node.action_id} missing preferred_lane"


def test_default_path_points_at_bundled_file() -> None:
    assert default_capabilities_path().name == "capabilities.yaml"
    assert default_capabilities_path().exists()


# ── repo resolution ──────────────────────────────────────────────────────────────


def test_unknown_owner_repo_fails_closed(tmp_path: Path) -> None:
    bad = _VALID_DOC.replace("owner_repo_id: custodian", "owner_repo_id: nope_repo")
    with pytest.raises(RepoGraphConfigError):
        load_capabilities(_write(tmp_path, bad))


def test_resolve_repos_false_skips_repo_check(tmp_path: Path) -> None:
    bad = _VALID_DOC.replace("owner_repo_id: custodian", "owner_repo_id: nope_repo")
    # repo_id targets are syntactically fine; only resolution against the map fails,
    # so skipping resolution lets the doc compile.
    registry = load_capabilities(_write(tmp_path, bad), resolve_repos=False)
    assert registry.owner_of("demo_audit") == "nope_repo"


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(RepoGraphConfigError):
        load_capabilities(tmp_path / "absent.yaml")


# ── CLI ──────────────────────────────────────────────────────────────────────────


def test_register_capability_commands_attaches_both_commands() -> None:
    import typer
    from rich.console import Console

    fresh = typer.Typer()
    capabilities_cli.register_capability_commands(fresh, Console())
    names = {cmd.name for cmd in fresh.registered_commands}
    assert {"capabilities", "capability"} <= names


def test_target_label_covers_all_scope_kinds() -> None:
    registry = load_default_capabilities()
    labels = {n.action_id: capabilities_cli._target_label(n) for n in registry.list_capabilities()}
    assert labels["board_unblock"] == "fleet"
    assert labels["repo_health_audit"].startswith("repo_set:")


def test_cli_capabilities_lists_all_seeds() -> None:
    result = CliRunner().invoke(app, ["capabilities"])
    assert result.exit_code == 0
    out = _strip_ansi(result.stdout)
    # rich truncates columns; match on stable prefixes.
    assert "board_unb" in out
    assert "repo_heal" in out
    assert "session_gc" in out


def test_cli_capability_show_renders_edges() -> None:
    result = CliRunner().invoke(app, ["capability", "board_unblock"])
    assert result.exit_code == 0
    out = _strip_ansi(result.stdout)
    assert "Board Unblock" in out
    assert "owns" in out
    assert "operations_center" in out


def test_cli_capability_unknown_exits_nonzero() -> None:
    result = CliRunner().invoke(app, ["capability", "does_not_exist"])
    assert result.exit_code == 1
    assert "unknown capability" in _strip_ansi(result.stdout)


def test_cli_capabilities_custom_path(tmp_path: Path) -> None:
    path = _write(tmp_path, _VALID_DOC)
    result = CliRunner().invoke(app, ["capabilities", "--capabilities", str(path)])
    assert result.exit_code == 0
    assert "demo_audit" in _strip_ansi(result.stdout)


def test_cli_capabilities_bad_registry_exits_2(tmp_path: Path) -> None:
    bad = _VALID_DOC.replace("owner_repo_id: custodian", "owner_repo_id: nope_repo")
    path = _write(tmp_path, bad)
    result = CliRunner().invoke(app, ["capabilities", "--capabilities", str(path)])
    assert result.exit_code == 2
