# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 ProtocolWarden
"""Validation helpers imported from RepoGraph."""

from __future__ import annotations

from .._repograph import import_repograph

_validation = import_repograph("repograph.ontology.validation")

parse_visibility = _validation.parse_visibility
parse_kind = _validation.parse_kind
parse_plane = _validation.parse_plane
parse_owner_kind = _validation.parse_owner_kind
enforce_platform_public_only = _validation.enforce_platform_public_only
parse_entity_projection_behavior = _validation.parse_entity_projection_behavior
