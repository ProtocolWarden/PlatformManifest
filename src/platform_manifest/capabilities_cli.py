# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 ProtocolWarden
"""Capability registry read-model CLI commands.

Registered onto the main ``platform-manifest`` app by ``cli.register_capability_commands``.
Kept out of ``cli.py`` so that entrypoint stays focused on the repo-map commands.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .capabilities import default_capabilities_path, load_capabilities
from .errors import RepoGraphConfigError


def _target_label(node) -> str:
    scope = node.target_scope
    if scope.kind.value == "repo":
        return f"repo:{scope.repo_id}"
    if scope.kind.value == "repo_set":
        sel = ", ".join(f"{k}={v}" for k, v in scope.selector) or "*"
        return f"repo_set:{sel}"
    return "fleet"


def register_capability_commands(app: typer.Typer, console: Console) -> None:
    """Attach the ``capabilities`` and ``capability`` commands to *app*."""

    def _registry(capabilities: Path | None):
        path = capabilities or default_capabilities_path()
        try:
            return load_capabilities(path)
        except RepoGraphConfigError as exc:
            console.print(f"[red]capability registry error:[/red] {exc}")
            raise typer.Exit(code=2) from exc

    @app.command("capabilities")
    def capabilities_cmd(
        capabilities: Path | None = typer.Option(
            None, "--capabilities", help="capability registry YAML path"
        ),
    ) -> None:
        """List fleet capabilities from the read-model registry."""
        registry = _registry(capabilities)
        table = Table(title="Platform Capabilities")
        for column in ("action_id", "owner", "target", "category", "risk", "lane"):
            table.add_column(column)
        for node in registry.list_capabilities():
            table.add_row(
                node.action_id,
                registry.owner_of(node.action_id) or "-",
                _target_label(node),
                node.category.value,
                node.risk.value,
                node.preferred_lane or "-",
            )
        console.print(table)

    @app.command("capability")
    def capability_cmd(
        action_id: str = typer.Argument(..., help="capability action_id to show"),
        capabilities: Path | None = typer.Option(
            None, "--capabilities", help="capability registry YAML path"
        ),
    ) -> None:
        """Show one capability and its typed edges."""
        registry = _registry(capabilities)
        node = registry.capability(action_id)
        if node is None:
            console.print(f"[red]unknown capability:[/red] {action_id}")
            raise typer.Exit(code=1)

        console.print(f"[bold]{node.action_id}[/bold] — {node.name}")
        if node.description:
            console.print(node.description)
        console.print(f"  owner         : {registry.owner_of(action_id) or '-'}")
        console.print(f"  target        : {_target_label(node)}")
        console.print(f"  category      : {node.category.value}")
        console.print(f"  risk          : {node.risk.value}")
        console.print(f"  preferred_lane: {node.preferred_lane or '-'}")
        console.print(
            f"  invocation    : {node.invocation.kind.value} → {node.invocation.ref}"
        )
        console.print(f"  visibility    : {node.visibility.value}")
        edges = Table(title="edges")
        edges.add_column("kind")
        edges.add_column("target")
        for edge in registry.edges_for(action_id):
            edges.add_row(edge.kind.value, edge.target_id)
        console.print(edges)
