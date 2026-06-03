# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| `main`  | ✅ Yes     |

Only the current `main` branch receives security fixes.

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Report security issues privately by emailing **coding.projects.1642@proton.me**.

Include:
- A description of the vulnerability
- Steps to reproduce
- Potential impact
- Any suggested mitigations (optional)

You will receive an acknowledgment within 72 hours. We aim to release a fix within 14 days of a confirmed report, depending on severity and complexity.

## Scope

PlatformManifest is a read-only repo map. The relevant security surface is small:

- **YAML parser misuse** — the loader uses `yaml.safe_load`; PRs must not switch to `yaml.load` or unsafe loaders
- **Path traversal in custom-config loading** — `load_repo_graph(path)` accepts an arbitrary path; consumers must validate operator-supplied paths before calling
- **Supply chain** — package data (`data/repo_graph.yaml`) ships with the wheel; tampering with the manifest could mislead downstream impact queries

## Out of Scope

- Vulnerabilities in PyYAML, Typer, or Rich (report upstream)
- Issues in consumer repos (OperationsCenter, SwitchBoard, OperatorConsole) — report there
- Build/CI tooling unrelated to manifest correctness
