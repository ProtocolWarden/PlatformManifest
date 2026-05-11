# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 ProtocolWarden
"""Custodian-facing visibility policy descriptors."""

from __future__ import annotations

from dataclasses import dataclass


PUBLIC_FORBIDDEN_FIELDS: frozenset[str] = frozenset({
    "cache_path",
    "endpoint_override",
    "env_file",
    "gpu_required",
    "internal_path",
    "local_path",
    "local_port",
    "private_artifact_locations",
    "private_bindings",
    "private_deployment_topology",
    "private_environment_assumptions",
    "private_policy_notes",
    "private_url",
    "restricted_relationship_edges",
    "runtime_hints",
})


@dataclass(frozen=True)
class CustodianCheckDescriptor:
    """A detector input PlatformManifest expects Custodian to enforce."""

    check_id: str
    description: str


PUBLIC_PROJECTION_CHECKS: tuple[CustodianCheckDescriptor, ...] = (
    CustodianCheckDescriptor(
        "public-manifest-private-repo-name",
        "Does a public manifest leak private repo names?",
    ),
    CustodianCheckDescriptor(
        "public-manifest-private-url",
        "Does a public manifest expose private URLs?",
    ),
    CustodianCheckDescriptor(
        "public-artifact-internal-path",
        "Does a public artifact reference internal paths?",
    ),
    CustodianCheckDescriptor(
        "readme-private-topology-term",
        "Does a README contain private topology terms?",
    ),
    CustodianCheckDescriptor(
        "public-manifest-private-binding",
        "Does a generated manifest expose private bindings?",
    ),
    CustodianCheckDescriptor(
        "public-schema-private-uri",
        "Does a public schema reference a private-only schema URI?",
    ),
    CustodianCheckDescriptor(
        "public-repo-private-deployment-detail",
        "Does a public repo include private deployment details?",
    ),
    CustodianCheckDescriptor(
        "public-relationship-projection-policy",
        "Does a public relationship edge violate projection policy?",
    ),
)


def custodian_policy_manifest() -> dict[str, object]:
    """Return a stable policy descriptor for Custodian integration."""
    return {
        "policy_owner": "PlatformManifest",
        "policy": "public_private_projection",
        "unknown_visibility": "private",
        "unknown_field_policy": "drop",
        "forbidden_public_fields": sorted(PUBLIC_FORBIDDEN_FIELDS),
        "checks": [
            {
                "check_id": check.check_id,
                "description": check.description,
            }
            for check in PUBLIC_PROJECTION_CHECKS
        ],
    }
