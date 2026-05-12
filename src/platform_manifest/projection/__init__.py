# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 ProtocolWarden
"""Projection helpers imported from RepoGraph."""

from __future__ import annotations

from .._repograph import import_repograph

_projection = import_repograph("repograph.projection")

ProjectionBehavior = _projection.ProjectionBehavior
ProjectionProfile = _projection.ProjectionProfile
PUBLIC_RELATIONSHIP_BEHAVIORS = _projection.PUBLIC_RELATIONSHIP_BEHAVIORS
can_project_node = _projection.can_project_node
can_project_relationship = _projection.can_project_relationship
default_projection_behavior_for_visibility = _projection.default_projection_behavior_for_visibility
parse_projection_behavior = _projection.parse_projection_behavior
public_name = _projection.public_name
to_public_manifest_dict = _projection.to_public_manifest_dict

__all__ = [
    "ProjectionBehavior",
    "ProjectionProfile",
    "PUBLIC_RELATIONSHIP_BEHAVIORS",
    "can_project_node",
    "can_project_relationship",
    "default_projection_behavior_for_visibility",
    "parse_projection_behavior",
    "public_name",
    "to_public_manifest_dict",
]
