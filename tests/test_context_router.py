# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 ProtocolWarden
"""Tests for the context-injection router prototype (.context/.engine/route.py).

Pure routing logic: glob matching, all-matches selection, budget + priority,
engine_compat degradation, and ## Inject extraction. No hook wiring is tested
(the engine ships dark; wiring is a later, gated phase).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_ENGINE = Path(__file__).resolve().parent.parent / ".context" / ".engine" / "route.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("cl_route", _ENGINE)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    # Register before exec so the frozen dataclass can resolve its module's
    # namespace (dataclasses introspects sys.modules[cls.__module__]).
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


route = _load_module()


# --- glob matching -------------------------------------------------------

@pytest.mark.parametrize(
    "glob,target,expected",
    [
        ("src/platform_manifest/loader.py", "src/platform_manifest/loader.py", True),
        ("src/platform_manifest/loader.py", "src/platform_manifest/cli.py", False),
        ("src/platform_manifest/projection/**", "src/platform_manifest/projection/rules.py", True),
        ("src/platform_manifest/projection/**", "src/platform_manifest/projection/a/b.py", True),
        ("src/platform_manifest/projection/**", "src/platform_manifest/projection", True),
        ("src/platform_manifest/projection/**", "src/platform_manifest/topology/x.py", False),
        ("src/platform_manifest/schemas/*.json", "src/platform_manifest/schemas/x.json", True),
        ("src/platform_manifest/schemas/*.json", "src/platform_manifest/schemas/sub/x.json", False),
        ("scripts/provision*.sh", "scripts/provision.sh", True),
        ("scripts/provision*.sh", "scripts/provision-machine.sh", True),
        ("scripts/provision*.sh", "scripts/clone-repos.sh", False),
    ],
)
def test_glob_to_regex(glob, target, expected):
    assert bool(route._glob_to_regex(glob).match(target)) is expected


# --- version range -------------------------------------------------------

def test_version_in_range():
    assert route._version_in_range((0, 2), ">=0.2 <0.3") is True
    assert route._version_in_range((0, 3), ">=0.2 <0.3") is False
    assert route._version_in_range((0, 1), ">=0.2 <0.3") is False
    assert route._version_in_range((0, 2), "") is False          # missing → degrade
    assert route._version_in_range((0, 2), "garbage") is False    # unparseable → degrade


# --- all-matches selection, priority, budget -----------------------------

def _routes():
    return [
        route.Route(match="src/a/**", inject=("docs/a.md", "docs/shared.md"), priority=20),
        route.Route(match="src/a/x.py", inject=("docs/x.md",), priority=10),
        route.Route(match="src/b/**", inject=("docs/b.md",), priority=5),
    ]

def test_all_matches_fires_every_rule_and_dedupes():
    # src/a/x.py matches both the glob rule and the exact rule.
    docs = route.select_docs("src/a/x.py", _routes(), max_docs=0)
    assert docs == ["docs/x.md", "docs/a.md", "docs/shared.md"]  # priority 10 then 20, deduped

def test_no_match_returns_empty():
    assert route.select_docs("src/c/y.py", _routes(), max_docs=0) == []

def test_budget_caps_by_priority():
    docs = route.select_docs("src/a/x.py", _routes(), max_docs=2)
    assert docs == ["docs/x.md", "docs/a.md"]  # lowest-priority-number wins, capped at 2

def test_leading_dot_slash_normalised():
    docs = route.select_docs("./src/b/z.py", _routes(), max_docs=0)
    assert docs == ["docs/b.md"]


# --- ## Inject extraction ------------------------------------------------

def test_extract_inject_only(tmp_path):
    doc = tmp_path / "leaf.md"
    doc.write_text(
        "<!-- c -->\n"
        "## Inject\n- keep this\n- and this\n\n"
        "## Reference\n- DROP this reference line\n"
    )
    body = route.extract_inject(doc)
    assert "keep this" in body
    assert "and this" in body
    assert "DROP this" not in body

def test_extract_inject_missing_section(tmp_path):
    doc = tmp_path / "leaf.md"
    doc.write_text("## Reference\nonly reference here\n")
    assert route.extract_inject(doc) == ""


# --- end-to-end against the real repo routes -----------------------------

def test_build_context_real_routes_matches_loader():
    root = Path(__file__).resolve().parent.parent
    block = route.build_context("src/platform_manifest/loader.py", root)
    assert "loader.py" in block
    assert "Fail-closed on visibility" in block  # real leaf-doc content
    # ## Reference content must NOT be injected
    assert "default_config_path()" not in block

def test_build_context_unknown_path_is_empty():
    root = Path(__file__).resolve().parent.parent
    assert route.build_context("README.md", root) == ""


# --- leaf-doc anti-staleness guard ---------------------------------------
# The spec's chief worry is stale knowledge. Leaf docs name src symbols as
# real conventions; if a rename silently breaks that, the doc lies. These
# imports from the platform_manifest package fail loudly if a named symbol
# disappears, keeping the injected conventions honest.

def test_leaf_docs_reference_real_src_symbols():
    from platform_manifest.errors import RepoGraphConfigError
    from platform_manifest.loader import default_config_path
    from platform_manifest.ontology import enforce_platform_public_only

    assert RepoGraphConfigError is not None
    assert callable(default_config_path)
    assert callable(enforce_platform_public_only)
