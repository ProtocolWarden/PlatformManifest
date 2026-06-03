# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 ProtocolWarden
"""Projection model types imported from RepoGraph."""

from __future__ import annotations

from .._repograph import import_repograph

_models = import_repograph("repograph.projection.models")

ProjectionBehavior = _models.ProjectionBehavior
ProjectionProfile = _models.ProjectionProfile
ProjectionProfileKind = _models.ProjectionProfileKind
ProjectionProfileRules = _models.ProjectionProfileRules
DEFAULT_PROJECTION_PROFILE_RULES = _models.DEFAULT_PROJECTION_PROFILE_RULES
build_projection_profile = _models.build_projection_profile
