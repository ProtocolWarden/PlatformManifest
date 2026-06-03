# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 ProtocolWarden
"""Projection rules imported from RepoGraph."""

from __future__ import annotations

from .._repograph import import_repograph

_rules = import_repograph("repograph.projection.rules")

PUBLIC_RELATIONSHIP_BEHAVIORS = _rules.PUBLIC_RELATIONSHIP_BEHAVIORS
default_projection_behavior_for_visibility = _rules.default_projection_behavior_for_visibility
