# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Velascat
"""Platform Manifest CLI — `platform-manifest`.

Read-only inspection of the platform repo map. Subcommands:
  list            — show canonical repos
  resolve NAME    — resolve canonical or legacy name
  upstream ID     — direct upstream nodes
  downstream ID   — direct downstream nodes
  impact ID       — repos affected by a contract change in ID
  validate PATH   — validate a manifest file against its schema + loader
"""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .loader import default_config_path, load_repo_graph
from .models import ManifestKind, RepoGraphConfigError
from .validate import validate_manifest

app = typer.Typer(help="Platform Manifest — repo map inspection.")
_console = Console()


_default_config_path = default_config_path  # back-compat alias for tests


def _load(config: Path | None):
    path = config or default_config_path()
    try:
        return load_repo_graph(path)
    except RepoGraphConfigError as exc:
        _console.print(f"[red]repo graph config error:[/red] {exc}")
        raise typer.Exit(code=2) from exc


@app.command("list")
def list_cmd(
    config: Path | None = typer.Option(None, "--config", help="repo graph YAML path"),
) -> None:
    """List known repos."""
    graph = _load(config)
    table = Table(title="Platform Repo Map")
    table.add_column("repo_id")
    table.add_column("canonical")
    table.add_column("legacy")
    table.add_column("role")
    for node in graph.list_nodes():
        table.add_row(
            node.repo_id,
            node.canonical_name,
            ", ".join(node.legacy_names) or "-",
            node.runtime_role or "-",
        )
    _console.print(table)


@app.command("resolve")
def resolve_cmd(
    name: str,
    config: Path | None = typer.Option(None, "--config"),
) -> None:
    """Resolve a canonical or legacy name."""
    graph = _load(config)
    node = graph.resolve(name)
    if node is None:
        _console.print(f"[red]not found:[/red] {name}")
        raise typer.Exit(code=1)
    _console.print(
        f"{name} → [cyan]{node.canonical_name}[/cyan] "
        f"(repo_id={node.repo_id}, role={node.runtime_role or '-'})"
    )


@app.command("upstream")
def upstream_cmd(
    repo_id: str,
    config: Path | None = typer.Option(None, "--config"),
) -> None:
    """Direct upstream nodes from repo_id."""
    graph = _load(config)
    try:
        nodes = graph.upstream(repo_id)
    except KeyError:
        _console.print(f"[red]unknown repo_id:[/red] {repo_id}")
        raise typer.Exit(code=1)
    for node in nodes:
        _console.print(f"  → {node.canonical_name} ({node.repo_id})")


@app.command("downstream")
def downstream_cmd(
    repo_id: str,
    config: Path | None = typer.Option(None, "--config"),
) -> None:
    """Direct downstream nodes pointing at repo_id."""
    graph = _load(config)
    try:
        nodes = graph.downstream(repo_id)
    except KeyError:
        _console.print(f"[red]unknown repo_id:[/red] {repo_id}")
        raise typer.Exit(code=1)
    for node in nodes:
        _console.print(f"  ← {node.canonical_name} ({node.repo_id})")


@app.command("impact")
def impact_cmd(
    repo_id: str,
    config: Path | None = typer.Option(None, "--config"),
) -> None:
    """Repos affected if `repo_id`'s contracts change."""
    graph = _load(config)
    try:
        nodes = graph.affected_by_contract_change(repo_id)
    except KeyError:
        _console.print(f"[red]unknown repo_id:[/red] {repo_id}")
        raise typer.Exit(code=1)
    if not nodes:
        _console.print("(no consumers)")
        return
    for node in nodes:
        _console.print(f"  • {node.canonical_name} ({node.repo_id})")


@app.command("validate")
def validate_cmd(
    path: Path = typer.Argument(..., help="Path to a manifest YAML file."),
    expected: str | None = typer.Option(
        None,
        "--expected",
        "-e",
        help="Enforce this manifest_kind (platform | project | local). "
             "When omitted, the kind is auto-detected from the file header.",
    ),
    json_output: bool = typer.Option(
        False, "--json", help="Emit the report as JSON for CI consumption."
    ),
    against: Path | None = typer.Option(
        None,
        "--against",
        help="For project manifests only: validate by composing against this "
             "platform manifest path. Defaults to the bundled platform_manifest.yaml.",
    ),
) -> None:
    """Validate a manifest file against its schema + loader rules.

    Two-stage check: JSON Schema (clean field-level errors) followed by
    the Python loader (catches semantic issues like duplicate names,
    private nodes in a platform manifest, or project edges that
    reference unknown nodes). Exits non-zero on any issue.

    Project manifests are validated in composition with the bundled
    platform base by default; pass ``--against PATH`` to use a custom
    platform base (e.g. when testing against a forked PlatformManifest).
    """
    expected_kind: ManifestKind | None = None
    if expected is not None:
        try:
            expected_kind = ManifestKind(expected)
        except ValueError as exc:
            allowed = [k.value for k in ManifestKind]
            _console.print(
                f"[red]--expected must be one of {allowed}; got {expected!r}[/red]"
            )
            raise typer.Exit(code=2) from exc

    report = validate_manifest(path, expected=expected_kind, against_platform=against)

    if json_output:
        typer.echo(json.dumps(report.to_dict(), indent=2))
    else:
        kind_str = report.detected_kind.value if report.detected_kind else "unknown"
        if report.ok:
            _console.print(f"[green]✓[/green] {path} ({kind_str}) — clean")
        else:
            _console.print(f"[red]✗[/red] {path} ({kind_str}) — {len(report.issues)} issue(s)")
            for issue in report.issues:
                loc = f" at {issue.json_path}" if issue.json_path else ""
                _console.print(f"  [{issue.severity}]{issue.message}{loc}")

    if not report.ok:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
