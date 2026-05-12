# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 ProtocolWarden
"""Compatibility facade over RepoGraph."""

from __future__ import annotations

from ._repograph import import_repograph

_repograph = import_repograph("repograph")

RepoGraphConfigError = _repograph.RepoGraphConfigError
EntityKind = _repograph.EntityKind
LOCAL_ANNOTATION_FIELDS = _repograph.LOCAL_ANNOTATION_FIELDS
ManifestHeader = _repograph.ManifestHeader
ManifestKind = _repograph.ManifestKind
OwnerKind = _repograph.OwnerKind
PlatformPlane = _repograph.PlatformPlane
PrivateManifest = import_repograph("repograph.ontology.models").PrivateManifest
ProjectionBehavior = _repograph.ProjectionBehavior
RepoNode = _repograph.RepoNode
Source = _repograph.Source
Visibility = _repograph.Visibility
default_projection_behavior_for_visibility = _repograph.default_projection_behavior_for_visibility
EdgeCategory = _repograph.EdgeCategory
EffectiveRepoGraph = _repograph.RepoGraph
OntologyRelationship = _repograph.OntologyRelationship
OntologyRelationshipKind = _repograph.OntologyRelationshipKind
RELATIONSHIP_EDGE_CATEGORIES = _repograph.RELATIONSHIP_EDGE_CATEGORIES
RepoEdge = _repograph.RepoEdge
RepoEdgeType = _repograph.RepoEdgeType
RepoGraph = _repograph.RepoGraph

MetadataValue = str | int | float | bool

__all__ = [
    "EdgeCategory",
    "EffectiveRepoGraph",
    "EntityKind",
    "LOCAL_ANNOTATION_FIELDS",
    "ManifestHeader",
    "ManifestKind",
    "MetadataValue",
    "OntologyRelationship",
    "OntologyRelationshipKind",
    "OwnerKind",
    "PlatformPlane",
    "PrivateManifest",
    "ProjectionBehavior",
    "RELATIONSHIP_EDGE_CATEGORIES",
    "RepoEdge",
    "RepoEdgeType",
    "RepoGraph",
    "RepoGraphConfigError",
    "RepoNode",
    "Source",
    "Visibility",
    "default_projection_behavior_for_visibility",
]
