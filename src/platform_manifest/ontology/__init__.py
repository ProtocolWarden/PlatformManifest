# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 ProtocolWarden
"""Ontology vocabulary and entity models for PlatformManifest."""

from .enums import (
    EntityKind,
    ManifestKind,
    OwnerKind,
    PlatformPlane,
    Source,
    Visibility,
)
from .models import LOCAL_ANNOTATION_FIELDS, ManifestHeader, MetadataValue, PrivateManifest, RepoNode
from .validation import (
    enforce_platform_public_only,
    parse_entity_projection_behavior,
    parse_kind,
    parse_owner_kind,
    parse_plane,
    parse_visibility,
)

__all__ = [
    "EntityKind",
    "LOCAL_ANNOTATION_FIELDS",
    "ManifestHeader",
    "ManifestKind",
    "MetadataValue",
    "OwnerKind",
    "PlatformPlane",
    "PrivateManifest",
    "RepoNode",
    "Source",
    "Visibility",
    "enforce_platform_public_only",
    "parse_entity_projection_behavior",
    "parse_kind",
    "parse_owner_kind",
    "parse_plane",
    "parse_visibility",
]
