# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 ProtocolWarden
"""Static checks for architecture documentation invariants."""

from __future__ import annotations

from pathlib import Path


DOC_ROOT = Path(__file__).resolve().parents[1] / "docs" / "architecture"


def _read_all_architecture_docs() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in DOC_ROOT.glob("*.md"))


def test_platform_manifest_boundary_invariants_remain_documented() -> None:
    docs = _read_all_architecture_docs()

    required = [
        "PlatformManifest owns what exists and what may be disclosed.",
        "CxRP owns execution/routing contract semantics.",
        "RxP owns runtime invocation semantics.",
        "OperationsCenter owns governance and orchestration implementation.",
        "ExecutorRuntime performs runtime invocation for OperationsCenter.",
        "WorkStation deploys and hosts runtime environments.",
        "VideoFoundry is a separate managed project and reference testbed.",
        "Custodian detects leaks and hygiene violations against declared policy.",
        "Private manifests are supersets.",
        "Public manifests are safe projections.",
        "Unknown visibility fails closed.",
        "Projection is policy-driven and testable.",
        "Contract schemas stay in their owning protocol repos.",
    ]

    for phrase in required:
        assert phrase in docs


def test_required_mermaid_diagrams_remain_documented() -> None:
    docs = _read_all_architecture_docs()

    required_markers = [
        "PM[PlatformManifest\\nTopology + Visibility + Entity Ontology]",
        "PrivateManifest[Private Manifest\\nFull internal truth]",
        "subgraph OntologyVisibility[Ontology + Visibility]",
        "sequenceDiagram",
        "PM --> EntityOntology[Platform Entity Ontology]",
    ]

    for marker in required_markers:
        assert marker in docs


def test_visibility_boundary_roles_remain_explicit() -> None:
    docs = _read_all_architecture_docs()

    assert "references CxRP and RxP rather than owning their schemas" in docs
    assert "VideoFoundry fits as an external managed project" in docs
    assert "WorkStation is the deployment and hosting layer" in docs
    assert "ExecutorRuntime is the runtime backend and driver" in docs
