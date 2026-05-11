# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 ProtocolWarden
"""Custodian policy descriptor tests."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from platform_manifest import PUBLIC_FORBIDDEN_FIELDS, custodian_policy_manifest
from platform_manifest.cli import app
from platform_manifest.custodian_native import _configured_forbidden_fields


def test_custodian_policy_manifest_exposes_projection_policy() -> None:
    policy = custodian_policy_manifest()

    assert policy["policy_owner"] == "PlatformManifest"
    assert policy["unknown_visibility"] == "private"
    assert policy["unknown_field_policy"] == "drop"
    assert "private_url" in policy["forbidden_public_fields"]
    assert "local_path" in policy["forbidden_public_fields"]
    check_ids = {check["check_id"] for check in policy["checks"]}
    assert "public-manifest-private-repo-name" in check_ids
    assert "public-relationship-projection-policy" in check_ids


def test_forbidden_public_fields_include_private_projection_surface() -> None:
    required = {
        "private_url",
        "internal_path",
        "private_bindings",
        "private_artifact_locations",
        "restricted_relationship_edges",
        "runtime_hints",
    }

    assert required.issubset(PUBLIC_FORBIDDEN_FIELDS)


def test_custodian_policy_cli_outputs_json() -> None:
    result = CliRunner().invoke(app, ["custodian-policy"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["policy_owner"] == "PlatformManifest"
    assert "checks" in payload


def test_custodian_native_defaults_to_policy_forbidden_fields() -> None:
    assert _configured_forbidden_fields({}) == PUBLIC_FORBIDDEN_FIELDS
