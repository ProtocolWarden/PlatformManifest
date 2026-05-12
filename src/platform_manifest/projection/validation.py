# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 ProtocolWarden
"""Projection validation imported from RepoGraph."""

from __future__ import annotations

from .._repograph import import_repograph

_validation = import_repograph("repograph.projection.validation")

parse_projection_behavior = _validation.parse_projection_behavior
can_project_node = _validation.can_project_node
can_project_relationship = _validation.can_project_relationship
