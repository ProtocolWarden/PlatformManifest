# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 ProtocolWarden
"""Context-injection router (PROTOTYPE).

Given a target file path, decide which warm leaf docs to inject, honouring:
  - all-matches routing (every matching rule fires, not first-match-wins)
  - an injection budget (max_docs_per_edit) with priority ordering
  - engine/routes version compatibility (engine_compat), degrading to NO
    injection on mismatch rather than misparsing

This is the PROTOTYPE home (`.context/.engine/`). Per the spec
(docs/architecture/context-injection-spec.md §1) the production engine is
authored in the ContextLifecycle repo and provisioned in; this local copy
exists to validate the design and ship dark behind `injection.enabled`.

Pure stdlib + PyYAML (already a project dependency). Never raises to its caller
in __main__: any failure prints nothing and exits 0, so it can never block a
tool call when wired into a hook.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

# Bump when the routes.yaml schema changes. routes.yaml carries an
# `engine_compat:` range; if this version is outside it, we degrade to no
# injection (§1 of the spec).
SCHEMA_VERSION = (0, 2)

ROUTES_FILE = "routes.yaml"
INJECT_HEADING = "## Inject"


@dataclass(frozen=True)
class Route:
    match: str
    inject: tuple[str, ...]
    priority: int  # lower = higher precedence when the budget truncates


def _glob_to_regex(glob: str) -> re.Pattern[str]:
    """Translate a path glob to a regex.

    Supports `**` (any number of path segments, including none) and `*` (any
    run of characters within a single segment). Anchored at both ends.
    """
    out: list[str] = ["^"]
    i = 0
    n = len(glob)
    while i < n:
        # `/**` — an optional subtree: matches the dir itself AND anything under
        # it. So `a/**` matches `a`, `a/b`, `a/b/c`.
        if glob[i] == "/" and glob[i + 1 : i + 3] == "**":
            out.append("(/.*)?")
            i += 3
            if i < n and glob[i] == "/":
                i += 1
            continue
        if glob[i] == "*":
            if i + 1 < n and glob[i + 1] == "*":
                # bare `**` (not preceded by `/`) — match across segments.
                out.append(".*")
                i += 2
                if i < n and glob[i] == "/":
                    i += 1
                continue
            out.append("[^/]*")
            i += 1
            continue
        out.append(re.escape(glob[i]))
        i += 1
    out.append("$")
    return re.compile("".join(out))


def _version_in_range(version: tuple[int, int], spec: str) -> bool:
    """Check a `>=A.B <C.D` range string against a (major, minor) version.

    Conservative: any unparseable spec returns False (degrade to no injection).
    """
    if not spec:
        return False
    ok = True
    for clause in spec.split():
        m = re.match(r"^(>=|<=|<|>|==)?(\d+)\.(\d+)$", clause.strip())
        if not m:
            return False
        op = m.group(1) or "=="
        bound = (int(m.group(2)), int(m.group(3)))
        if op == ">=":
            ok = ok and version >= bound
        elif op == "<=":
            ok = ok and version <= bound
        elif op == ">":
            ok = ok and version > bound
        elif op == "<":
            ok = ok and version < bound
        else:
            ok = ok and version == bound
    return ok


def load_routes(context_dir: Path) -> tuple[list[Route], int, bool]:
    """Load `<context_dir>/routes.yaml`.

    Returns (routes, max_docs_per_edit, compatible). On any problem (missing
    file, parse error, version mismatch) returns ([], 0, False) so callers
    degrade to no injection.
    """
    routes_path = context_dir / ROUTES_FILE
    try:
        data = yaml.safe_load(routes_path.read_text()) or {}
    except (OSError, yaml.YAMLError):
        return [], 0, False

    if not _version_in_range(SCHEMA_VERSION, str(data.get("engine_compat", ""))):
        return [], 0, False

    budget = data.get("budget", {}) or {}
    max_docs = int(budget.get("max_docs_per_edit", 0) or 0)

    routes: list[Route] = []
    for entry in data.get("routes", []) or []:
        match = entry.get("match")
        inject = entry.get("inject") or []
        if not match or not inject:
            continue
        routes.append(
            Route(
                match=match,
                inject=tuple(inject),
                priority=int(entry.get("priority", 100)),
            )
        )
    return routes, max_docs, True


def select_docs(target: str, routes: list[Route], max_docs: int) -> list[str]:
    """All-matches selection: every matching rule contributes its docs.

    Dedupe preserving first sight, order by ascending route priority, then cap
    at max_docs (0 = uncapped). Returns the doc paths that win.
    """
    target = target.lstrip("./")
    chosen: list[tuple[int, str]] = []
    seen: set[str] = set()
    for route in routes:
        if not _glob_to_regex(route.match).match(target):
            continue
        for doc in route.inject:
            if doc in seen:
                continue
            seen.add(doc)
            chosen.append((route.priority, doc))
    chosen.sort(key=lambda pd: pd[0])
    docs = [doc for _, doc in chosen]
    if max_docs and len(docs) > max_docs:
        docs = docs[:max_docs]
    return docs


def extract_inject(doc_path: Path) -> str:
    """Return the body of the `## Inject` section only (not `## Reference`)."""
    try:
        text = doc_path.read_text()
    except OSError:
        return ""
    lines = text.splitlines()
    out: list[str] = []
    capturing = False
    for line in lines:
        if line.strip().startswith("## "):
            capturing = line.strip() == INJECT_HEADING
            continue
        if capturing:
            out.append(line)
    return "\n".join(out).strip()


def build_context(target: str, root: Path) -> str:
    """Top-level: produce the injectable context block for `target`, or ''."""
    # Engine code lives in .context/.engine/; routes.yaml lives in .context/ (spec §1).
    routes, max_docs, compatible = load_routes(root / ".context")
    if not compatible or not routes:
        return ""
    docs = select_docs(target, routes, max_docs)
    if not docs:
        return ""

    blocks: list[str] = []
    dropped = 0
    for doc in docs:
        body = extract_inject(root / doc)
        if body:
            blocks.append(f"<!-- {doc} -->\n{body}")
        else:
            dropped += 1
    if not blocks:
        return ""

    header = f"Relevant conventions for `{target}` (injected before edit):"
    note = ""
    if dropped:
        note = f"\n\n[router: {dropped} matched doc(s) had no ## Inject section]"
    return header + "\n\n" + "\n\n".join(blocks) + note


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Context-injection router")
    parser.add_argument("--target", required=True, help="repo-relative file path being edited")
    parser.add_argument("--root", default=".", help="repo root (CL_ANCHOR)")
    args = parser.parse_args(argv)
    try:
        block = build_context(args.target, Path(args.root))
    except Exception:  # never blocks a hook: any failure → no output, exit 0
        return 0
    if block:
        sys.stdout.write(block + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
