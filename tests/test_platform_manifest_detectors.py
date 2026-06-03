# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 ProtocolWarden
"""PlatformManifest-native detector tests."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from platform_manifest.custodian_native import detect_pmv1, detect_pmv2


def _context(repo_root: Path) -> object:
    return SimpleNamespace(
        repo_root=repo_root,
        config={"audit": {"platform_manifest": {}}},
    )


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_pmv2_flags_relationships_to_unknown_and_private_nodes(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "public_manifest.json",
        {
            "manifest_kind": "platform",
            "manifest_version": "1.0.0",
            "repos": {
                "public_docs": {"canonical_name": "PublicDocs", "visibility": "public"},
                "private_impl": {"canonical_name": "PrivateImpl", "visibility": "private"},
            },
            "edges": [],
            "relationships": [
                {
                    "id": "r1",
                    "source": "public_docs",
                    "target": "private_impl",
                    "kind": "documents",
                    "visibility": "public",
                    "projection_behavior": "public_safe",
                },
                {
                    "id": "r2",
                    "source": "public_docs",
                    "target": "ghost",
                    "kind": "documents",
                    "visibility": "public",
                    "projection_behavior": "public_safe",
                },
            ],
        },
    )

    result = detect_pmv2(_context(tmp_path))
    rendered = "\n".join(result.samples)
    assert result.count == 2
    assert "relationship references private node public_docs->private_impl" in rendered
    assert "relationship references non-public/unknown node public_docs->ghost" in rendered


def test_pmv2_flags_relationships_with_unsafe_projection_metadata(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "public_manifest.json",
        {
            "manifest_kind": "platform",
            "manifest_version": "1.0.0",
            "repos": {
                "public_docs": {"canonical_name": "PublicDocs", "visibility": "public"},
            },
            "edges": [],
            "relationships": [
                {
                    "id": "r1",
                    "source": "public_docs",
                    "target": "public_docs",
                    "kind": "documents",
                    "visibility": "private",
                    "projection_behavior": "private_only",
                }
            ],
        },
    )

    result = detect_pmv2(_context(tmp_path))
    rendered = "\n".join(result.samples)
    assert result.count == 2
    assert "relationship has non-public visibility 'private'" in rendered
    assert "relationship has unsafe projection_behavior 'private_only'" in rendered


# ---------------------------------------------------------------------------
# PMV1 — forbidden fields and private paths
# ---------------------------------------------------------------------------

def test_pmv1_passes_when_manifest_is_clean(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "public_manifest.json",
        {
            "manifest_kind": "platform",
            "manifest_version": "1.0.0",
            "repos": {
                "public_docs": {"canonical_name": "PublicDocs", "visibility": "public"},
            },
            "edges": [],
        },
    )
    result = detect_pmv1(_context(tmp_path))
    assert result.count == 0


def test_pmv1_flags_forbidden_field_in_manifest(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "public_manifest.json",
        {
            "manifest_kind": "platform",
            "repos": {
                "my_repo": {
                    "canonical_name": "MyRepo",
                    "visibility": "public",
                    "local_path": "/home/dev/private/myrepo",
                },
            },
            "edges": [],
        },
    )
    result = detect_pmv1(_context(tmp_path))
    assert result.count >= 1
    assert any("local_path" in s for s in result.samples)


def test_pmv1_flags_internal_path_value(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "public_manifest.json",
        {
            "manifest_kind": "platform",
            "repos": {
                "my_repo": {
                    "canonical_name": "MyRepo",
                    "visibility": "public",
                    "artifact_url": "/home/dev/artifacts/bundle.tar.gz",
                },
            },
            "edges": [],
        },
    )
    result = detect_pmv1(_context(tmp_path))
    assert result.count >= 1
    assert any("internal path" in s for s in result.samples)


def test_pmv1_skips_when_no_manifest_file_present(tmp_path: Path) -> None:
    result = detect_pmv1(_context(tmp_path))
    assert result.count == 0


def test_pmv1_flags_private_term_when_configured(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "public_manifest.json",
        {
            "manifest_kind": "platform",
            "repos": {
                "my_repo": {
                    "canonical_name": "MyRepo",
                    "visibility": "public",
                    "description": "Uses SecretProject infrastructure.",
                },
            },
            "edges": [],
        },
    )
    ctx = SimpleNamespace(
        repo_root=tmp_path,
        config={"audit": {"platform_manifest": {"private_terms": ["SecretProject"]}}},
    )
    result = detect_pmv1(ctx)
    assert result.count >= 1
    assert any("SecretProject" in s for s in result.samples)
