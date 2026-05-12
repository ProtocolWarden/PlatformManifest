# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 ProtocolWarden
"""Topology edge vocabulary, graph models, and validation."""

from .edges import EdgeCategory, OntologyRelationshipKind, RELATIONSHIP_EDGE_CATEGORIES, RepoEdgeType
from .models import EffectiveRepoGraph, OntologyRelationship, RepoEdge, RepoGraph
from .validation import (
    RepoGraphConfigError,
    parse_relationship_kind,
    parse_relationship_projection_behavior,
    parse_repo_edge_type,
    validate_graph_topology,
)

__all__ = [
    "EdgeCategory",
    "EffectiveRepoGraph",
    "OntologyRelationship",
    "OntologyRelationshipKind",
    "RELATIONSHIP_EDGE_CATEGORIES",
    "RepoEdge",
    "RepoEdgeType",
    "RepoGraph",
    "RepoGraphConfigError",
    "parse_relationship_kind",
    "parse_relationship_projection_behavior",
    "parse_repo_edge_type",
    "validate_graph_topology",
]
