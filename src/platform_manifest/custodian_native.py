# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 ProtocolWarden
"""Custodian-native detector contributor owned by PlatformManifest."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

from .custodian import PUBLIC_FORBIDDEN_FIELDS

_MAX_SAMPLES = 12
_URL_RE = re.compile(r"https?://[^\s\"']+", re.IGNORECASE)
_INTERNAL_PATH_RE = re.compile(
    r"(?:^|[\"':\s])(?:/(?:home|Users|opt|var|tmp)/[^\s\"']+|[A-Za-z]:\\\\[^\s\"']+)"
)
_PRIVATE_URL_RE = re.compile(
    r"https?://(?:[^/\s\"']+\.)?(?:github|gitlab|bitbucket)\.com/"
    r"(?:private|internal|[^/\s\"']*(?:private|internal)[^/\s\"']*)/",
    re.IGNORECASE,
)


def build_custodian_detectors() -> list[object]:
    """Return Custodian detector instances when Custodian is installed."""
    from custodian.audit_kit.detector import Detector, HIGH

    detectors = [
        Detector(
            "PMV1",
            "public PlatformManifest projection leaks forbidden private fields or values",
            "open",
            detect_pmv1,
            HIGH,
        ),
        Detector(
            "PMV2",
            "public PlatformManifest projection contains relationship edges to private nodes",
            "open",
            detect_pmv2,
            HIGH,
        ),
    ]
    for detector in detectors:
        detector.source = "custom"
    return detectors


def detect_pmv1(context) -> object:
    from custodian.audit_kit.detector import DetectorResult

    cfg = _platform_manifest_cfg(context)
    forbidden_fields = set(_configured_forbidden_fields(cfg))
    private_terms = set(_configured_private_terms(cfg))
    samples: list[str] = []

    for path in _manifest_paths(context, cfg):
        payload = _read_structured(path)
        if payload is None:
            continue
        rel = _rel(context, path)
        for json_path, key, value in _walk(payload):
            if key in forbidden_fields:
                samples.append(f"{rel}:{json_path}: forbidden public field `{key}`")
            if isinstance(value, str):
                if _PRIVATE_URL_RE.search(value):
                    samples.append(f"{rel}:{json_path}: private URL `{value}`")
                elif _URL_RE.search(value) and _looks_private(value):
                    samples.append(f"{rel}:{json_path}: private-looking URL `{value}`")
                if _INTERNAL_PATH_RE.search(value):
                    samples.append(f"{rel}:{json_path}: internal path `{value}`")
                lower = value.lower()
                for term in private_terms:
                    if term.lower() in lower:
                        samples.append(f"{rel}:{json_path}: private term `{term}`")

    return DetectorResult(count=len(samples), samples=samples[:_MAX_SAMPLES])


def detect_pmv2(context) -> object:
    from custodian.audit_kit.detector import DetectorResult

    cfg = _platform_manifest_cfg(context)
    samples: list[str] = []

    for path in _manifest_paths(context, cfg):
        payload = _read_structured(path)
        if not isinstance(payload, dict):
            continue
        rel = _rel(context, path)
        repos = payload.get("repos") or {}
        if not isinstance(repos, dict):
            continue
        private_repo_ids = {
            str(repo_id)
            for repo_id, fields in repos.items()
            if isinstance(fields, dict) and fields.get("visibility") != "public"
        }
        public_repo_ids = {
            str(repo_id)
            for repo_id, fields in repos.items()
            if isinstance(fields, dict) and fields.get("visibility") == "public"
        }
        for idx, edge in enumerate(payload.get("edges") or []):
            if not isinstance(edge, dict):
                continue
            src = str(edge.get("from", ""))
            dst = str(edge.get("to", ""))
            if src in private_repo_ids or dst in private_repo_ids:
                samples.append(f"{rel}:$.edges[{idx}]: edge references private node {src}->{dst}")
            elif src and dst and (src not in public_repo_ids or dst not in public_repo_ids):
                samples.append(
                    f"{rel}:$.edges[{idx}]: edge references non-public/unknown node {src}->{dst}"
                )
        for idx, relationship in enumerate(payload.get("relationships") or []):
            if not isinstance(relationship, dict):
                continue
            src = str(relationship.get("source", ""))
            dst = str(relationship.get("target", ""))
            visibility = relationship.get("visibility")
            projection_behavior = relationship.get("projection_behavior")
            if visibility != "public":
                samples.append(
                    f"{rel}:$.relationships[{idx}]: relationship has non-public visibility "
                    f"{visibility!r}"
                )
            if projection_behavior not in ("public_safe", "redacted_public_stub"):
                samples.append(
                    f"{rel}:$.relationships[{idx}]: relationship has unsafe projection_behavior "
                    f"{projection_behavior!r}"
                )
            if src in private_repo_ids or dst in private_repo_ids:
                samples.append(
                    f"{rel}:$.relationships[{idx}]: relationship references private node "
                    f"{src}->{dst}"
                )
            elif src and dst and (src not in public_repo_ids or dst not in public_repo_ids):
                samples.append(
                    f"{rel}:$.relationships[{idx}]: relationship references "
                    f"non-public/unknown node {src}->{dst}"
                )

    return DetectorResult(count=len(samples), samples=samples[:_MAX_SAMPLES])


def _platform_manifest_cfg(context) -> dict[str, Any]:
    audit_cfg = context.config.get("audit") or {}
    cfg = audit_cfg.get("platform_manifest") or {}
    return cfg if isinstance(cfg, dict) else {}


def _manifest_paths(context, cfg: dict[str, Any]) -> list[Path]:
    configured = cfg.get("public_manifest_paths") or []
    paths: list[Path] = []
    if isinstance(configured, str):
        configured = [configured]
    if isinstance(configured, list):
        for item in configured:
            if isinstance(item, str) and item:
                path = Path(item)
                paths.append(path if path.is_absolute() else context.repo_root / path)
    if paths:
        return paths

    defaults = [
        context.repo_root / "public_manifest.json",
        context.repo_root / "public_manifest.yaml",
        context.repo_root / "topology" / "public_manifest.json",
        context.repo_root / "topology" / "public_manifest.yaml",
    ]
    return [path for path in defaults if path.exists()]


def _configured_forbidden_fields(cfg: dict[str, Any]) -> frozenset[str]:
    configured = cfg.get("forbidden_public_fields")
    if isinstance(configured, list) and all(isinstance(item, str) for item in configured):
        return frozenset(configured)
    return PUBLIC_FORBIDDEN_FIELDS


def _configured_private_terms(cfg: dict[str, Any]) -> frozenset[str]:
    configured = cfg.get("private_terms") or []
    if isinstance(configured, list) and all(isinstance(item, str) for item in configured):
        return frozenset(item for item in configured if item)
    return frozenset()


def _read_structured(path: Path) -> Any | None:
    if not path.exists():
        return None
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    try:
        if path.suffix.lower() == ".json":
            return json.loads(raw)
        return yaml.safe_load(raw)
    except (json.JSONDecodeError, yaml.YAMLError):
        return None


def _walk(value: Any, path: str = "$") -> list[tuple[str, str | None, Any]]:
    out: list[tuple[str, str | None, Any]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_str = str(key)
            child_path = f"{path}.{key_str}"
            out.append((child_path, key_str, child))
            out.extend(_walk(child, child_path))
    elif isinstance(value, list):
        for idx, child in enumerate(value):
            out.extend(_walk(child, f"{path}[{idx}]"))
    return out


def _looks_private(value: str) -> bool:
    lowered = value.lower()
    return any(marker in lowered for marker in ("/private/", "/internal/", "github.com/private"))


def _rel(context, path: Path) -> str:
    try:
        return str(path.relative_to(context.repo_root))
    except ValueError:
        return str(path)
