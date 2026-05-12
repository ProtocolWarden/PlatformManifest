# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 ProtocolWarden
"""Topology models and graph queries imported from RepoGraph."""

from __future__ import annotations

from .._repograph import import_repograph

_models = import_repograph("repograph.topology.models")

RepoEdge = _models.RepoEdge
OntologyRelationship = _models.OntologyRelationship
RepoGraph = _models.RepoGraph
EffectiveRepoGraph = _models.RepoGraph
