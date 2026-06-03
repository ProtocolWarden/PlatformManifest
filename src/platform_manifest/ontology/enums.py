# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 ProtocolWarden
"""Canonical ontology vocabulary imported from RepoGraph."""

from __future__ import annotations

from .._repograph import import_repograph

_ontology = import_repograph("repograph.ontology.enums")

ManifestKind = _ontology.ManifestKind
Visibility = _ontology.Visibility
Source = _ontology.Source
PlatformPlane = _ontology.PlatformPlane
OwnerKind = _ontology.OwnerKind
EntityKind = _ontology.EntityKind
