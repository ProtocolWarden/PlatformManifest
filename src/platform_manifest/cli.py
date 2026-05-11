# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 ProtocolWarden
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
from .projection import to_public_manifest_dict
from .custodian import custodian_policy_manifest
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
        help="Enforce this manifest_kind (platform | project | work_scope | local). "
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
        typer.echo(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
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


@app.command("effective")
def effective_cmd(
    project: Path | None = typer.Option(
        None, "--project", help="Project manifest YAML path (mutually exclusive with --work-scope)."
    ),
    private: Path | None = typer.Option(
        None, "--private", help="Private manifest YAML path layered after the public platform base."
    ),
    work_scope: Path | None = typer.Option(
        None, "--work-scope", help="WorkScopeManifest YAML path (mutually exclusive with --project)."
    ),
    local: Path | None = typer.Option(
        None, "--local", help="Local manifest YAML path (optional)."
    ),
    base: Path | None = typer.Option(
        None,
        "--base",
        help="Override the platform base; defaults to the bundled platform_manifest.yaml.",
    ),
    json_output: bool = typer.Option(
        False, "--json", help="Emit the merged graph as JSON for automation."
    ),
) -> None:
    """Show the merged EffectiveRepoGraph — what OC actually consumes.

    Composes the platform base + optional project + optional local
    layers exactly as ``OperationsCenter.repo_graph_factory`` does at
    runtime. Use this to inspect what your OC instance will see for a
    given configuration before running a real dispatch.

    Without arguments, prints the platform-only graph (same as ``list``
    but with provenance + local annotations exposed).
    """
    from .composition import load_effective_graph

    base_path = base or default_config_path()
    try:
        graph = load_effective_graph(
            base_path, private=private, project=project, work_scope=work_scope, local=local
        )
    except RepoGraphConfigError as exc:
        _console.print(f"[red]composition error:[/red] {exc}")
        raise typer.Exit(code=2) from exc

    if json_output:
        payload: dict[str, object] = {
            "base": str(base_path),
            "project": str(project) if project else None,
            "private": str(private) if private else None,
            "work_scope": str(work_scope) if work_scope else None,
            "local": str(local) if local else None,
            "nodes": [
                {
                    "repo_id": n.repo_id,
                    "canonical_name": n.canonical_name,
                    "visibility": n.visibility.value,
                    "kind": n.kind,
                    "owner": n.owner,
                    "scope": n.scope,
                    "source": n.source.value,
                    "runtime_role": n.runtime_role,
                    "legacy_names": list(n.legacy_names),
                    "github_url": n.github_url,
                    "metadata": dict(n.metadata),
                    "projection_policy": n.projection_policy,
                    "projection_behavior": n.projection_behavior.value,
                    "public_alias": n.public_alias,
                    "redaction_label": n.redaction_label,
                    "private_binding_refs": list(n.private_binding_refs),
                    "local_overlay_refs": list(n.local_overlay_refs),
                    "local_path": n.local_path,
                    "local_port": n.local_port,
                    "env_file": n.env_file,
                    "endpoint_override": n.endpoint_override,
                    "cache_path": n.cache_path,
                    "gpu_required": n.gpu_required,
                    "runtime_hints": dict(n.runtime_hints),
                }
                for n in graph.list_nodes()
            ],
            "edges": [
                {"from": e.src, "to": e.dst, "type": e.type.value, "source": e.source.value}
                for e in graph.edges
            ],
            "relationships": [
                {
                    "id": r.relationship_id,
                    "source": r.source_id,
                    "target": r.target_id,
                    "kind": r.kind.value,
                    "visibility": r.visibility.value,
                    "projection_behavior": r.projection_behavior.value,
                    "policy_ref": r.policy_ref,
                    "redaction_label": r.redaction_label,
                    "metadata": dict(r.metadata),
                    "source_manifest": r.source.value,
                }
                for r in graph.list_relationships()
            ],
        }
        typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    nodes_table = Table(title="Effective Repo Graph — Nodes")
    nodes_table.add_column("repo_id")
    nodes_table.add_column("canonical")
    nodes_table.add_column("vis")
    nodes_table.add_column("source")
    nodes_table.add_column("role")
    nodes_table.add_column("local")
    for node in graph.list_nodes():
        local_bits: list[str] = []
        if node.local_path:
            local_bits.append(f"path={node.local_path}")
        if node.local_port:
            local_bits.append(f"port={node.local_port}")
        if node.gpu_required:
            local_bits.append("gpu")
        if node.endpoint_override:
            local_bits.append(f"ep={node.endpoint_override}")
        nodes_table.add_row(
            node.repo_id,
            node.canonical_name,
            node.visibility.value,
            node.source.value,
            node.runtime_role or "-",
            ", ".join(local_bits) or "-",
        )
    _console.print(nodes_table)

    edges_table = Table(title="Effective Repo Graph — Edges")
    edges_table.add_column("from")
    edges_table.add_column("to")
    edges_table.add_column("type")
    edges_table.add_column("source")
    for edge in graph.edges:
        edges_table.add_row(edge.src, edge.dst, edge.type.value, edge.source.value)
    _console.print(edges_table)


@app.command("project-public")
def project_public_cmd(
    private: Path | None = typer.Option(
        None,
        "--private",
        help="Private manifest YAML path layered after the public platform base.",
    ),
    project: Path | None = typer.Option(
        None,
        "--project",
        help="Project manifest YAML path (mutually exclusive with --work-scope).",
    ),
    work_scope: Path | None = typer.Option(
        None,
        "--work-scope",
        help="WorkScopeManifest YAML path (mutually exclusive with --project).",
    ),
    local: Path | None = typer.Option(
        None,
        "--local",
        help="Local manifest YAML path. Accepted to prove local fields are dropped.",
    ),
    base: Path | None = typer.Option(
        None,
        "--base",
        help="Override the platform base; defaults to the bundled platform_manifest.yaml.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Write the projected public manifest JSON to this path instead of stdout.",
    ),
) -> None:
    """Generate a public manifest projection from private/effective input.

    This command always validates. Unsafe generation lives on the explicit
    `project-public-unsafe` developer-only command.
    """
    from .composition import load_effective_graph

    base_path = base or default_config_path()
    try:
        graph = load_effective_graph(
            base_path, private=private, project=project, work_scope=work_scope, local=local
        )
    except RepoGraphConfigError as exc:
        _console.print(f"[red]composition error:[/red] {exc}")
        raise typer.Exit(code=2) from exc

    projected = to_public_manifest_dict(graph)
    rendered = json.dumps(projected, indent=2, ensure_ascii=False)
    from tempfile import NamedTemporaryFile

    with NamedTemporaryFile("w", encoding="utf-8", suffix=".json") as tmp:
        tmp.write(rendered)
        tmp.flush()
        report = validate_manifest(Path(tmp.name), expected=ManifestKind.PLATFORM)
    if not report.ok:
        for issue in report.issues:
            loc = f" at {issue.json_path}" if issue.json_path else ""
            _console.print(f"  [{issue.severity}]{issue.message}{loc}")
        raise typer.Exit(code=1)
    if output is not None:
        output.write_text(rendered + "\n", encoding="utf-8")
    else:
        typer.echo(rendered)


@app.command("project-public-unsafe")
def project_public_unsafe_cmd(
    private: Path | None = typer.Option(
        None,
        "--private",
        help="Private manifest YAML path layered after the public platform base.",
    ),
    project: Path | None = typer.Option(
        None,
        "--project",
        help="Project manifest YAML path (mutually exclusive with --work-scope).",
    ),
    work_scope: Path | None = typer.Option(
        None,
        "--work-scope",
        help="WorkScopeManifest YAML path (mutually exclusive with --project).",
    ),
    local: Path | None = typer.Option(
        None,
        "--local",
        help="Local manifest YAML path. Accepted to prove local fields are dropped.",
    ),
    base: Path | None = typer.Option(
        None,
        "--base",
        help="Override the platform base; defaults to the bundled platform_manifest.yaml.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Write the projected public manifest JSON to this path instead of stdout.",
    ),
) -> None:
    """Developer-only unsafe public projection helper. Does not validate output."""
    from .composition import load_effective_graph

    _console.print(
        "[yellow]warning:[/yellow] project-public-unsafe skips validation and "
        "must not be used for release or publication workflows."
    )
    base_path = base or default_config_path()
    try:
        graph = load_effective_graph(
            base_path, private=private, project=project, work_scope=work_scope, local=local
        )
    except RepoGraphConfigError as exc:
        _console.print(f"[red]composition error:[/red] {exc}")
        raise typer.Exit(code=2) from exc

    projected = to_public_manifest_dict(graph)
    rendered = json.dumps(projected, indent=2, ensure_ascii=False)
    if output is not None:
        output.write_text(rendered + "\n", encoding="utf-8")
    else:
        typer.echo(rendered)


@app.command("custodian-policy")
def custodian_policy_cmd() -> None:
    """Emit the PlatformManifest visibility policy descriptor for Custodian."""
    typer.echo(json.dumps(custodian_policy_manifest(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    app()
