# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 ProtocolWarden
"""Entity-shaped ontology models imported from RepoGraph."""

from __future__ import annotations

from .._repograph import import_repograph

_models = import_repograph("repograph.ontology.models")

MetadataValue = _models.MetadataValue
LOCAL_ANNOTATION_FIELDS = _models.LOCAL_ANNOTATION_FIELDS
ManifestHeader = _models.ManifestHeader
RepoNode = _models.RepoNode
PrivateManifest = _models.PrivateManifest
