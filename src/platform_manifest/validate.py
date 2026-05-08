# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Velascat
"""Manifest validation — JSON Schema + Python loader.

Public entry point:
    validate_manifest(path, *, expected=None) -> ValidationReport

Two-stage validation:
1. JSON Schema (the published contract — clean field-level errors)
2. Python loader (catches semantic issues — duplicate names, edges to
   unknown nodes, private nodes in platform manifests, local-only
   fields outside LocalManifest, etc.)

Local manifests are schema-only — they're annotation layers and only
make sense in composition with a base graph; standalone semantic
validation is just the schema's allowlist check.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from .composition import load_effective_graph
from .loader import default_config_path, load_repo_graph
from .models import ManifestKind, RepoGraphConfigError


@dataclass(frozen=True)
class ValidationIssue:
    """One validation finding."""

    severity: str  # "schema" | "loader" | "io"
    message: str
    json_path: str | None = None  # e.g. "$.repos.oc.canonical_name"

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"severity": self.severity, "message": self.message}
        if self.json_path is not None:
            out["json_path"] = self.json_path
        return out


@dataclass(frozen=True)
class ValidationReport:
    """Outcome of validating a single manifest file."""

    path: Path
    detected_kind: ManifestKind | None
    issues: tuple[ValidationIssue, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return len(self.issues) == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "detected_kind": self.detected_kind.value if self.detected_kind else None,
            "ok": self.ok,
            "issues": [i.to_dict() for i in self.issues],
        }


_SCHEMA_FILES: dict[ManifestKind, str] = {
    ManifestKind.PLATFORM: "platform_manifest.schema.json",
    ManifestKind.PROJECT: "project_manifest.schema.json",
    ManifestKind.WORK_SCOPE: "work_scope_manifest.schema.json",
    ManifestKind.LOCAL: "local_manifest.schema.json",
}


def validate_manifest(
    path: Path,
    *,
    expected: ManifestKind | None = None,
    against_platform: Path | None = None,
) -> ValidationReport:
    """Validate one manifest file.

    ``expected`` enforces the slot — when set, mismatch between the
    file's ``manifest_kind`` and ``expected`` is reported as an issue.
    When None, the kind is auto-detected from the file header.

    ``against_platform`` is used only for project manifests: project
    manifests reference platform nodes (e.g. edges to ``OperationsCenter``),
    so standalone loader-stage validation fails on cross-layer references.
    Project manifests are validated by composing against this platform
    base. Defaults to the bundled ``platform_manifest.yaml``.
    """
    path = Path(path)

    raw_text, io_issue = _read_file(path)
    if io_issue is not None:
        return ValidationReport(path=path, detected_kind=None, issues=(io_issue,))

    raw, parse_issue = _parse_yaml(raw_text)
    if parse_issue is not None:
        return ValidationReport(path=path, detected_kind=None, issues=(parse_issue,))

    detected, kind_issue = _detect_kind(raw)
    if detected is None:
        return ValidationReport(path=path, detected_kind=None, issues=(kind_issue,))

    issues: list[ValidationIssue] = []

    # Slot enforcement
    if expected is not None and detected is not expected:
        issues.append(ValidationIssue(
            severity="schema",
            message=(
                f"manifest_kind={detected.value!r} does not match "
                f"expected={expected.value!r}"
            ),
            json_path="$.manifest_kind",
        ))
        # Don't continue validating against the wrong-kind schema —
        # the message would just be noise.
        return ValidationReport(path=path, detected_kind=detected, issues=tuple(issues))

    # Stage 1: JSON Schema
    issues.extend(_validate_against_schema(raw, kind=detected))

    # Stage 2: Python loader.
    # - PLATFORM: standalone loader (it's the base; no cross-layer refs).
    # - PROJECT:  compose against the bundled platform base (or
    #             against_platform override) so project edges referencing
    #             platform nodes resolve correctly.
    # - LOCAL:    skipped — annotation-only; needs a base to validate.
    if not issues:
        if detected is ManifestKind.PLATFORM:
            loader_issue = _validate_via_loader(path, kind=detected)
            if loader_issue is not None:
                issues.append(loader_issue)
        elif detected is ManifestKind.PROJECT:
            base = against_platform or default_config_path()
            loader_issue = _validate_project_in_composition(path, base=base)
            if loader_issue is not None:
                issues.append(loader_issue)
        elif detected is ManifestKind.WORK_SCOPE:
            base = against_platform or default_config_path()
            loader_issue = _validate_work_scope_in_composition(path, base=base)
            if loader_issue is not None:
                issues.append(loader_issue)

    return ValidationReport(path=path, detected_kind=detected, issues=tuple(issues))


# ---------------------------------------------------------------------------
# Stage helpers
# ---------------------------------------------------------------------------


def _read_file(path: Path) -> tuple[str, ValidationIssue | None]:
    if not path.exists():
        return "", ValidationIssue(severity="io", message=f"file not found: {path}")
    try:
        return path.read_text(encoding="utf-8"), None
    except OSError as exc:
        return "", ValidationIssue(severity="io", message=f"could not read {path}: {exc}")


def _parse_yaml(raw_text: str) -> tuple[dict[str, Any], ValidationIssue | None]:
    try:
        data = yaml.safe_load(raw_text) or {}
    except yaml.YAMLError as exc:
        return {}, ValidationIssue(severity="schema", message=f"YAML parse error: {exc}")
    if not isinstance(data, dict):
        return {}, ValidationIssue(
            severity="schema",
            message="manifest root must be a mapping",
            json_path="$",
        )
    return data, None


def _detect_kind(
    raw: dict[str, Any],
) -> tuple[ManifestKind | None, ValidationIssue | None]:
    kind_raw = raw.get("manifest_kind")
    if kind_raw is None:
        return None, ValidationIssue(
            severity="schema",
            message="missing required field 'manifest_kind'",
            json_path="$.manifest_kind",
        )
    try:
        return ManifestKind(kind_raw), None
    except ValueError:
        allowed = [k.value for k in ManifestKind]
        return None, ValidationIssue(
            severity="schema",
            message=f"unknown manifest_kind={kind_raw!r}; allowed: {allowed}",
            json_path="$.manifest_kind",
        )


def _validate_against_schema(
    raw: dict[str, Any],
    *,
    kind: ManifestKind,
) -> list[ValidationIssue]:
    schema = _load_schema(kind)
    validator = Draft202012Validator(schema)
    issues: list[ValidationIssue] = []
    for err in sorted(validator.iter_errors(raw), key=lambda e: list(e.absolute_path)):
        issues.append(ValidationIssue(
            severity="schema",
            message=err.message,
            json_path=_format_json_path(err),
        ))
    return issues


def _load_schema(kind: ManifestKind) -> dict[str, Any]:
    filename = _SCHEMA_FILES[kind]
    raw = (resources.files("platform_manifest.schemas") / filename).read_text(
        encoding="utf-8"
    )
    return json.loads(raw)


def _format_json_path(err: ValidationError) -> str:
    parts: list[str] = ["$"]
    for p in err.absolute_path:
        parts.append(f"[{p!r}]" if isinstance(p, int) else f".{p}")
    return "".join(parts)


def _validate_via_loader(path: Path, *, kind: ManifestKind) -> ValidationIssue | None:
    try:
        load_repo_graph(path, expected_kind=kind)
    except RepoGraphConfigError as exc:
        return ValidationIssue(severity="loader", message=str(exc))
    return None


def _validate_project_in_composition(
    path: Path,
    *,
    base: Path,
) -> ValidationIssue | None:
    """Compose project against the platform base to validate cross-layer refs."""
    try:
        load_effective_graph(base, project=path)
    except RepoGraphConfigError as exc:
        return ValidationIssue(severity="loader", message=str(exc))
    return None


def _validate_work_scope_in_composition(
    path: Path,
    *,
    base: Path,
) -> ValidationIssue | None:
    """Compose work-scope against the platform base. Validates includes
    resolve, no platform-to-platform edges, no repo_id collisions, etc."""
    try:
        load_effective_graph(base, work_scope=path)
    except RepoGraphConfigError as exc:
        return ValidationIssue(severity="loader", message=str(exc))
    return None


__all__ = [
    "ValidationIssue",
    "ValidationReport",
    "validate_manifest",
]
