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
        # `/**` — a subtree wildcard.
        if glob[i] == "/" and glob[i + 1 : i + 3] == "**":
            # Trailing `/**` is an OPTIONAL subtree: matches the dir itself AND
            # anything under it. So `a/**` matches `a`, `a/b`, `a/b/c`.
            # An interior `/**/` (e.g. `a/**/b`) must keep the path structure
            # around it: it matches zero or more intervening segments but still
            # requires the separators, so `a/**/b` matches `a/b`, `a/x/b` but
            # NOT `ab`.
            if i + 3 < n and glob[i + 3] == "/":
                out.append("/(.*/)?")
                i += 4
                continue
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
    try:
        max_docs = int(budget.get("max_docs_per_edit", 0) or 0)
    except (TypeError, ValueError):
        # Malformed budget (e.g. a YAML typo `max_docs_per_edit: foo`) →
        # uncapped rather than raising out of a fail-closed loader.
        max_docs = 0

    routes: list[Route] = []
    for entry in data.get("routes", []) or []:
        match = entry.get("match")
        inject = entry.get("inject") or []
        if not match or not inject:
            continue
        try:
            priority = int(entry.get("priority", 100))
        except (TypeError, ValueError):
            # Malformed priority (e.g. `priority: high`) → default precedence
            # rather than raising out of a fail-closed loader.
            priority = 100
        routes.append(
            Route(
                match=match,
                inject=tuple(inject),
                priority=priority,
            )
        )
    return routes, max_docs, True


def select_docs(target: str, routes: list[Route], max_docs: int) -> list[str]:
    """All-matches selection: every matching rule contributes its docs.

    Convenience wrapper around :func:`select_docs_split` that returns only the
    kept docs (the ones that win the budget). See that function for the dedupe
    and ordering semantics.
    """
    kept, _dropped = select_docs_split(target, routes, max_docs)
    return kept


def select_docs_split(
    target: str, routes: list[Route], max_docs: int
) -> tuple[list[str], list[str]]:
    """All-matches selection, returning (kept, budget_dropped).

    Every matching rule contributes its docs. A doc injected by several routes
    is deduped and ranked by the MINIMUM priority across all matching routes
    (lower number = higher precedence), so a specific high-precedence route
    wins over a broad low-precedence one that merely mentions the doc first.
    Order by ascending priority, then cap at max_docs (non-positive = uncapped;
    a negative value is NOT used as a slice index). `budget_dropped` lists the
    docs cut by the cap, in priority order, so the caller can report them
    (spec §3: no silent truncation).
    """
    # Strip only a leading literal "./" prefix — NOT a character set, which
    # would mangle dot-prefixed paths like ".github/...".
    if target.startswith("./"):
        target = target[2:]
    best: dict[str, int] = {}
    order: list[str] = []
    for route in routes:
        if not _glob_to_regex(route.match).match(target):
            continue
        for doc in route.inject:
            if doc not in best:
                best[doc] = route.priority
                order.append(doc)
            elif route.priority < best[doc]:
                best[doc] = route.priority
    # Stable sort by priority, preserving first-sight order within a tie.
    order.sort(key=lambda doc: best[doc])
    if max_docs > 0 and len(order) > max_docs:
        return order[:max_docs], order[max_docs:]
    return order, []


# Sentinel distinguishing "file does not exist / unreadable" (a route config
# error) from "file exists but has no ## Inject content" (an empty section).
MISSING_DOC = "\x00MISSING"


def extract_inject(doc_path: Path) -> str:
    """Return the body of the `## Inject` section only (not `## Reference`).

    Returns ``MISSING_DOC`` when the file does not exist or is unreadable (a
    broken route, distinct from a present-but-empty section which returns '').
    """
    try:
        text = doc_path.read_text()
    except OSError:
        return MISSING_DOC
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
    docs, over_budget = select_docs_split(target, routes, max_docs)
    if not docs:
        return ""

    blocks: list[str] = []
    empty: list[str] = []
    missing: list[str] = []
    for doc in docs:
        body = extract_inject(root / doc)
        if body == MISSING_DOC:
            missing.append(doc)
        elif body:
            blocks.append(f"<!-- {doc} -->\n{body}")
        else:
            empty.append(doc)

    # Diagnostics — surfaced even when every matched doc was unusable, so a
    # fully broken route set is distinguishable from a no-match (which returns
    # '' earlier). Spec §3: no silent truncation.
    notes: list[str] = []
    if empty:
        notes.append(f"[router: {len(empty)} matched doc(s) had no ## Inject section]")
    if missing:
        notes.append(
            f"[router: {len(missing)} matched doc(s) not found (broken route): "
            f"{', '.join(missing)}]"
        )
    if over_budget:
        notes.append(
            f"[router: dropped {len(over_budget)} over-budget doc(s): "
            f"{', '.join(over_budget)}]"
        )

    note = ("\n\n" + "\n".join(notes)) if notes else ""
    if not blocks:
        # Nothing injectable, but report why if there is anything to say.
        return note.lstrip("\n") if notes else ""

    header = f"Relevant conventions for `{target}` (injected before edit):"
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
