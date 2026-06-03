# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 ProtocolWarden
# ruff: noqa: S101
"""Smoke tests for the RepoGraph re-exporter bridge modules.

These modules are thin wrappers over `import_repograph()` — they
re-export symbols from the sibling RepoGraph checkout. Tests here
verify that each symbol is accessible and has the right type (class,
callable, dict, etc.) without re-testing RepoGraph's own logic.
"""
from __future__ import annotations

import inspect


# ---------------------------------------------------------------------------
# _repograph: import helper
# ---------------------------------------------------------------------------

def test_import_repograph_loads_module() -> None:
    from platform_manifest._repograph import import_repograph
    mod = import_repograph("repograph")
    assert mod is not None
    assert hasattr(mod, "RepoGraphConfigError")


# ---------------------------------------------------------------------------
# errors: RepoGraphConfigError re-export
# ---------------------------------------------------------------------------

def test_repograph_config_error_is_exception() -> None:
    from platform_manifest.errors import RepoGraphConfigError
    assert issubclass(RepoGraphConfigError, Exception)


# ---------------------------------------------------------------------------
# ontology/enums: vocabulary re-exports
# ---------------------------------------------------------------------------

def test_ontology_enums_accessible() -> None:
    from platform_manifest.ontology.enums import (
        EntityKind,
        ManifestKind,
        OwnerKind,
        PlatformPlane,
        Source,
        Visibility,
    )
    # Each should be an enum class
    assert inspect.isclass(ManifestKind)
    assert inspect.isclass(Visibility)
    assert inspect.isclass(Source)
    assert inspect.isclass(PlatformPlane)
    assert inspect.isclass(OwnerKind)
    assert inspect.isclass(EntityKind)


def test_visibility_has_public_member() -> None:
    from platform_manifest.ontology.enums import Visibility
    assert hasattr(Visibility, "PUBLIC") or any(
        v.value in ("public", "PUBLIC") for v in Visibility
    )


# ---------------------------------------------------------------------------
# ontology/models: model re-exports
# ---------------------------------------------------------------------------

def test_ontology_models_accessible() -> None:
    from platform_manifest.ontology.models import (
        LOCAL_ANNOTATION_FIELDS,
        ManifestHeader,
        MetadataValue,
        PrivateManifest,
        RepoNode,
    )
    assert inspect.isclass(ManifestHeader)
    assert inspect.isclass(RepoNode)
    assert inspect.isclass(PrivateManifest)
    assert LOCAL_ANNOTATION_FIELDS is not None
    assert MetadataValue is not None


# ---------------------------------------------------------------------------
# ontology/validation: parser re-exports
# ---------------------------------------------------------------------------

def test_ontology_validation_callables() -> None:
    from platform_manifest.ontology.validation import (
        enforce_platform_public_only,
        parse_entity_projection_behavior,
        parse_kind,
        parse_owner_kind,
        parse_plane,
        parse_visibility,
    )
    assert callable(parse_visibility)
    assert callable(parse_kind)
    assert callable(parse_plane)
    assert callable(parse_owner_kind)
    assert callable(enforce_platform_public_only)
    assert callable(parse_entity_projection_behavior)


def test_manifest_kind_has_platform_member() -> None:
    from platform_manifest.ontology.enums import ManifestKind
    values = {m.value for m in ManifestKind}
    assert "platform" in values or any("platform" in v for v in values)


# ---------------------------------------------------------------------------
# projection/models: model re-exports
# ---------------------------------------------------------------------------

def test_projection_models_accessible() -> None:
    from platform_manifest.projection.models import (
        DEFAULT_PROJECTION_PROFILE_RULES,
        ProjectionBehavior,
        ProjectionProfile,
        ProjectionProfileKind,
        ProjectionProfileRules,
        build_projection_profile,
    )
    assert inspect.isclass(ProjectionBehavior)
    assert inspect.isclass(ProjectionProfile)
    assert inspect.isclass(ProjectionProfileKind)
    assert inspect.isclass(ProjectionProfileRules)
    assert callable(build_projection_profile)
    assert DEFAULT_PROJECTION_PROFILE_RULES is not None


# ---------------------------------------------------------------------------
# projection/redaction: public_name re-export
# ---------------------------------------------------------------------------

def test_projection_redaction_public_name_callable() -> None:
    from platform_manifest.projection.redaction import public_name
    assert callable(public_name)


# ---------------------------------------------------------------------------
# projection/rules: rule re-exports
# ---------------------------------------------------------------------------

def test_projection_rules_accessible() -> None:
    from platform_manifest.projection.rules import (
        PUBLIC_RELATIONSHIP_BEHAVIORS,
        default_projection_behavior_for_visibility,
    )
    assert callable(default_projection_behavior_for_visibility)
    assert PUBLIC_RELATIONSHIP_BEHAVIORS is not None


# ---------------------------------------------------------------------------
# projection/validation: validator re-exports
# ---------------------------------------------------------------------------

def test_projection_validation_callables() -> None:
    from platform_manifest.projection.validation import (
        can_project_node,
        can_project_relationship,
        parse_projection_behavior,
    )
    assert callable(parse_projection_behavior)
    assert callable(can_project_node)
    assert callable(can_project_relationship)


# ---------------------------------------------------------------------------
# topology/edges: edge vocabulary re-exports
# ---------------------------------------------------------------------------

def test_topology_edges_accessible() -> None:
    from platform_manifest.topology.edges import (
        EdgeCategory,
        OntologyRelationshipKind,
        RELATIONSHIP_EDGE_CATEGORIES,
        RepoEdgeType,
    )
    assert inspect.isclass(EdgeCategory)
    assert inspect.isclass(OntologyRelationshipKind)
    assert inspect.isclass(RepoEdgeType)
    assert RELATIONSHIP_EDGE_CATEGORIES is not None


# ---------------------------------------------------------------------------
# topology/models: graph model re-exports
# ---------------------------------------------------------------------------

def test_topology_models_accessible() -> None:
    from platform_manifest.topology.models import (
        EffectiveRepoGraph,
        OntologyRelationship,
        RepoEdge,
        RepoGraph,
    )
    assert inspect.isclass(RepoEdge)
    assert inspect.isclass(OntologyRelationship)
    assert inspect.isclass(RepoGraph)
    assert inspect.isclass(EffectiveRepoGraph)


# ---------------------------------------------------------------------------
# topology/validation: validator re-exports
# ---------------------------------------------------------------------------

def test_topology_validation_callables() -> None:
    from platform_manifest.topology.validation import (
        parse_relationship_kind,
        parse_relationship_projection_behavior,
        parse_repo_edge_type,
        validate_graph_topology,
    )
    assert callable(parse_repo_edge_type)
    assert callable(parse_relationship_kind)
    assert callable(parse_relationship_projection_behavior)
    assert callable(validate_graph_topology)
