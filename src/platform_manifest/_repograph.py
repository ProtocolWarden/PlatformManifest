# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 ProtocolWarden
"""Import helper for the sibling RepoGraph checkout."""

from __future__ import annotations

import sys
from importlib import import_module
from pathlib import Path


def import_repograph(module_name: str):
    try:
        return import_module(module_name)
    except ModuleNotFoundError:
        repo_src = Path(__file__).resolve().parents[3] / "RepoGraph" / "src"
        if repo_src.is_dir():
            sys.path.insert(0, str(repo_src))
        return import_module(module_name)
