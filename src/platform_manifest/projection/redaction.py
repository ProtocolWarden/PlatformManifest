# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 ProtocolWarden
"""Redaction helpers imported from RepoGraph."""

from __future__ import annotations

from .._repograph import import_repograph

public_name = import_repograph("repograph.projection.redaction").public_name
