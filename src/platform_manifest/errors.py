# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 ProtocolWarden
"""Shared exceptions for PlatformManifest."""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from repograph import RepoGraphConfigError
except ModuleNotFoundError:
    repo_src = Path(__file__).resolve().parents[3] / "RepoGraph" / "src"
    if repo_src.is_dir():
        sys.path.insert(0, str(repo_src))
    from repograph import RepoGraphConfigError
