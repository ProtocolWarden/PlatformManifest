# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 ProtocolWarden
"""Shared exceptions for PlatformManifest.

`RepoGraphConfigError` is re-exported from the `repograph` package so the rest
of the codebase imports it from here without depending on RepoGraph's layout.
It is listed in `__all__` to mark it as an intentional re-export (ruff F401).
"""

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

__all__ = ["RepoGraphConfigError"]
