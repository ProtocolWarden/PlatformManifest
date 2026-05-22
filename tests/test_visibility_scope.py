"""Tests for the P2 manifest-cognition fields: visibility_scope, also_hosts."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from platform_manifest.errors import RepoGraphConfigError
from platform_manifest.loader import (
    default_config_path,
    load_repo_graph,
    parse_also_hosts,
    parse_visibility_scope,
    read_manifest_raw,
)


def _write(tmp_path: Path, payload: dict) -> Path:
    p = tmp_path / "manifest.yaml"
    p.write_text(yaml.safe_dump(payload), encoding="utf-8")
    return p


def test_bundled_platform_manifest_declares_visibility_scope_public():
    raw = read_manifest_raw(default_config_path())
    assert raw.get("visibility_scope") == "public"


def test_bundled_platform_manifest_loads_with_new_fields():
    # Backward-compat: loader.load_repo_graph must still succeed despite the
    # new top-level fields being present.
    g = load_repo_graph(default_config_path())
    assert len(g.nodes) > 0


def test_parse_visibility_scope_explicit_public(tmp_path):
    p = _write(tmp_path, {"visibility_scope": "public", "repos": {}})
    assert parse_visibility_scope(read_manifest_raw(p), path=p) == "public"


def test_parse_visibility_scope_explicit_private(tmp_path):
    p = _write(tmp_path, {"visibility_scope": "private", "repos": {}})
    assert parse_visibility_scope(read_manifest_raw(p), path=p) == "private"


def test_parse_visibility_scope_invalid_value(tmp_path):
    p = _write(tmp_path, {"visibility_scope": "weird", "repos": {}})
    with pytest.raises(RepoGraphConfigError, match="visibility_scope"):
        parse_visibility_scope(read_manifest_raw(p), path=p)


def test_parse_visibility_scope_derived_from_all_public_repos(tmp_path):
    p = _write(
        tmp_path,
        {
            "repos": {
                "a": {"canonical_name": "A", "visibility": "public"},
                "b": {"canonical_name": "B", "visibility": "public"},
            }
        },
    )
    assert parse_visibility_scope(read_manifest_raw(p), path=p) == "public"


def test_parse_visibility_scope_mixed_requires_explicit(tmp_path):
    p = _write(
        tmp_path,
        {
            "repos": {
                "a": {"canonical_name": "A", "visibility": "public"},
                "b": {"canonical_name": "B", "visibility": "private"},
            }
        },
    )
    with pytest.raises(RepoGraphConfigError, match="visibility_scope"):
        parse_visibility_scope(read_manifest_raw(p), path=p)


def test_parse_also_hosts_empty(tmp_path):
    p = _write(tmp_path, {"repos": {}})
    assert parse_also_hosts(read_manifest_raw(p), path=p) == []


def test_parse_also_hosts_valid(tmp_path):
    p = _write(
        tmp_path,
        {
            "repos": {},
            "also_hosts": [
                {"manifest": "Other", "repos": ["a", "b"]},
            ],
        },
    )
    out = parse_also_hosts(read_manifest_raw(p), path=p)
    assert out == [{"manifest": "Other", "repos": ["a", "b"]}]


def test_parse_also_hosts_missing_repos_defaults_empty(tmp_path):
    p = _write(
        tmp_path,
        {"repos": {}, "also_hosts": [{"manifest": "Other"}]},
    )
    out = parse_also_hosts(read_manifest_raw(p), path=p)
    assert out == [{"manifest": "Other", "repos": []}]


def test_parse_also_hosts_missing_manifest_errors(tmp_path):
    p = tmp_path / "m2.yaml"
    p.write_text(yaml.safe_dump({"also_hosts": [{"repos": ["a"]}]}), encoding="utf-8")
    with pytest.raises(RepoGraphConfigError, match="manifest"):
        parse_also_hosts(read_manifest_raw(p), path=p)
