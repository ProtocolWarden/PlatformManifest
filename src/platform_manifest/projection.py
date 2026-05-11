# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 ProtocolWarden
"""Public projection helpers for effective repo graphs."""

from __future__ import annotations

from typing import Any

from .models import ProjectionBehavior, RepoGraph, Visibility


_PUBLIC_RELATIONSHIP_BEHAVIORS: frozenset[ProjectionBehavior] = frozenset({
    ProjectionBehavior.PUBLIC_SAFE,
    ProjectionBehavior.REDACTED_PUBLIC_STUB,
})


def to_public_manifest_dict(
    graph: RepoGraph,
    *,
    manifest_version: str = "1.0.0",
) -> dict[str, Any]:
    """Project a graph into a public PlatformManifest-shaped dictionary.

    The projection is intentionally fail-closed:

    - only nodes marked public-safe are emitted;
    - only ontology relationships marked public-safe or redacted-public-stub
      are emitted;
    - only repo-graph edges whose endpoints survive projection are emitted;
    - local annotation fields are never emitted.
    """
    public_nodes = {
        repo_id: node
        for repo_id, node in graph.nodes.items()
        if node.visibility is Visibility.PUBLIC
        and node.projection_behavior is ProjectionBehavior.PUBLIC_SAFE
    }

    repos: dict[str, dict[str, Any]] = {}
    for repo_id, node in sorted(public_nodes.items()):
        fields: dict[str, Any] = {
            "canonical_name": node.public_alias or node.canonical_name,
            "visibility": Visibility.PUBLIC.value,
            "projection_behavior": ProjectionBehavior.PUBLIC_SAFE.value,
        }
        if node.kind.value != "Repository":
            fields["kind"] = node.kind.value
        if node.legacy_names:
            fields["legacy_names"] = list(node.legacy_names)
        if node.github_url:
            fields["github_url"] = node.github_url
        if node.runtime_role:
            fields["runtime_role"] = node.runtime_role
        if node.owner:
            fields["owner"] = node.owner
        if node.scope:
            fields["scope"] = node.scope
        if node.metadata:
            fields["metadata"] = dict(node.metadata)
        if node.public_alias:
            fields["public_alias"] = node.public_alias
        repos[repo_id] = fields

    edges = [
        {"from": edge.src, "to": edge.dst, "type": edge.type.value}
        for edge in graph.edges
        if edge.src in public_nodes and edge.dst in public_nodes
    ]

    relationships = [
        {
            "id": relationship.relationship_id,
            "source": relationship.source_id,
            "target": relationship.target_id,
            "kind": relationship.kind.value,
            "visibility": Visibility.PUBLIC.value,
            "projection_behavior": relationship.projection_behavior.value,
            **(
                {"policy_ref": relationship.policy_ref}
                if relationship.policy_ref
                else {}
            ),
            **(
                {"redaction_label": relationship.redaction_label}
                if relationship.redaction_label
                else {}
            ),
            **(
                {"metadata": dict(relationship.metadata)}
                if relationship.metadata
                else {}
            ),
        }
        for relationship in graph.list_relationships()
        if relationship.source_id in public_nodes
        and relationship.target_id in public_nodes
        and relationship.visibility is Visibility.PUBLIC
        and relationship.projection_behavior in _PUBLIC_RELATIONSHIP_BEHAVIORS
    ]

    return {
        "manifest_kind": "platform",
        "manifest_version": manifest_version,
        "repos": repos,
        "edges": edges,
        "relationships": relationships,
    }
