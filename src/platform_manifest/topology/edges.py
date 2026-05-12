# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 ProtocolWarden
"""Topology edge vocabulary imported from RepoGraph."""

from __future__ import annotations

from .._repograph import import_repograph

_edges = import_repograph("repograph.topology.edges")

EdgeCategory = _edges.EdgeCategory
OntologyRelationshipKind = _edges.OntologyRelationshipKind
RepoEdgeType = _edges.RepoEdgeType
RELATIONSHIP_EDGE_CATEGORIES = _edges.RELATIONSHIP_EDGE_CATEGORIES
