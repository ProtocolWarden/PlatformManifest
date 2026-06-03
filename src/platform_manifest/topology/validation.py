# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 ProtocolWarden
"""Topology validation imported from RepoGraph."""

from __future__ import annotations

from .._repograph import import_repograph

_validation = import_repograph("repograph.topology.validation")
RepoGraphConfigError = import_repograph("repograph").RepoGraphConfigError

parse_repo_edge_type = _validation.parse_repo_edge_type
parse_relationship_kind = _validation.parse_relationship_kind
parse_relationship_projection_behavior = _validation.parse_relationship_projection_behavior
validate_graph_topology = _validation.validate_graph_topology
