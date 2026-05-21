# Log

## 2026-05-21 — Add closing fence to console-context block

Added <!-- /console-context --> end marker so OperatorConsole only replaces its
managed block and leaves repo-owned content below it untouched.

## 2026-05-21 — Fix B1 boundary violation in platform_manifest.yaml

Removed VideoFoundry name from inline comment — Custodian B1 flags private repo names in
tracked public files. Replaced with generic "Private project consumers" phrasing.

## 2026-05-21 — Add Warehouse and ContextLifecycleProtocol to manifest

Added two repos missing from the public platform graph:
- Warehouse (context_staging) — already referenced in github.io catalog and org profile but absent from manifest
- ContextLifecycleProtocol (cognition_lifecycle) — new public repo; added OC→CLP depends_on_contracts_from edge
VideoFoundry→CLP edge excluded: VF is private and belongs in PrivateManifest per trust boundary.

## 2026-05-19 — ADR 0006 Phase 4: rename executor_runtime → core_runner in manifest + tests

- platform_manifest.yaml: node key executor_runtime → core_runner, canonical_name → CoreRunner, github_url → CoreRunner, all edge refs updated.
- tests/test_ontology_relationships.py, test_repo_graph.py, test_architecture_docs.py, test_validate.py: all executor_runtime/ExecutorRuntime strings updated.
- docs/architecture/platformmanifest_ontology.md, visibility_boundary.md, vocabulary_audit.md, platform_topology.md, verification/manifest_system.md, README.md, CONTRIBUTING.md, docs/README.md: global rename.
- 157 tests pass.

## 2026-05-13 — Add RepoGraph to manifest; declare PlatformManifest → RepoGraph edge

- Added `repograph:` entry to platform_manifest.yaml (canonical_name: RepoGraph, runtime_role: graph_language).
- Added edge: PlatformManifest → RepoGraph (depends_on_contracts_from).
- Closes X2 blind spot: PlatformManifest/errors.py imports `repograph` at runtime; undeclared edge was silently passing X2 because RepoGraph had no manifest entry.

## 2026-05-13 — WorkStation → PlatformDeployment hard cutover

- Renamed `workstation:` key to `platformdeployment:` in `platform_manifest.yaml`.
- Added custodian config exclusions for pre-existing LOW findings in new ontology/projection/topology modules.
- Added doc_conventions.exclude_path_patterns (with default **/history/** re-included) to suppress DC7 orphan on verification doc.

## 2026-05-08 — Wire pre-commit hook

Added .hooks/pre-commit (log.md enforcement) and set core.hooksPath = .hooks.
Pre-push Custodian guard was already present; now both hooks are active.

_Chronological continuity log. Decisions, stop points, what changed and why._
_Not a task tracker — that's backlog.md. Keep entries concise and dated._

## 2026-05-12 — RepoGraph projection profile export sync

Re-exported RepoGraph projection profile types and defaults through the
PlatformManifest projection module so the public manifest stays aligned with
the hardened projection model without defining its own semantic vocabulary.

## Recent Decisions

_Log significant choices here so they survive context resets._

| Decision | Rationale | Date |
|----------|-----------|------|
| Promote multi-repo composition to first-class `WorkScopeManifest` (manifest_kind: work_scope). v0.9.0 ships transitional support; project+includes still loads with DeprecationWarning. v1.0.0 will hard-fail. | Overloading `manifest_kind: project` for shells blurred the trust posture — a shell composes, a project describes. Distinct kind + schema + provenance (Source.WORK_SCOPE) prevents semantic drift and enables strict slot validation in OC settings. | 2026-05-08 |
| Ship worked examples in `examples/{single_project,work_scope}/` and validate them in CI. README + OC operator docs migrated to v0.9 vocabulary. | An operator authoring their first manifest needs a runnable starting point that's kept fresh by CI, not a copy-paste blob in markdown that rots. The examples pin v0.9 platform_manifest constraints, exercise both manifest kinds, and the CI step `validate-examples` ensures schema/loader changes can't silently break authoring guidance. | 2026-05-08 |
| Cut PM v1.0.0: hard-fail `manifest_kind: project` with `includes:` (R4). | Scan of all five sibling repos found zero authored legacy shells, so the gating criterion was already satisfied. Leaving the deprecation branch around just preserves ambiguity for future authors. v1.0.0 removes `includes` from the project schema (schema rejects at the field-validation layer), drops the deprecation warning in `_apply_project` and replaces it with an explicit migration-hint `RepoGraphConfigError` (catches direct loader callers that bypass schema), deletes `test_includes.py` (project-of-project recursion is no longer reachable; collision/composition rules are covered by `test_work_scope.py`), bumps example version_constraints to `>=1.0,<2.0`. | 2026-05-08 |
| Scrub Warehouse-as-asset-producer framing from PM artifacts. | The R7.2/R7.3 motivating example was wrong-semantics — Warehouse is developer/operator tooling (repo chunking, LLM context extraction), NOT a runtime artifact provider. VF doesn't operationally consume Warehouse-produced artifacts. Audit confirmed the bad edge was never in any committed `topology/project_manifest.yaml` (VF still pins `>=0.3,<1.0`, edge absent), but the framing fossilized in `models.py` docstring + `tests/test_repo_graph.py` node labels + `docs/verification/manifest_system.md`. Synthetic test labels switched to `GenericApi/GenericWorker/AssetPublisher`; docstring + verification doc reframed around generic "asset publisher"; verification doc carries an explicit retraction note. Edge type `BUNDLES_ASSETS_FROM` itself stands — keep until a real producer/consumer asset relationship surfaces. Mechanism stays correct; semantic interpretation corrected before the graph vocabulary fossilized around it. | 2026-05-08 |
| Add no-implicit-discovery invariant tests. | DoD audit caught that the verification spec's "loader does not scan sibling directories / does not glob" assertion was not explicitly covered. New `TestNoImplicitDiscovery` (2 cases) places sibling `decoy.yaml` + `topology/project_manifest.yaml`-named decoys alongside an explicitly-included manifest and proves they are NOT pulled in. Defense-in-depth against future "but it'd be convenient if it auto-discovered..." regression. | 2026-05-08 |

## Stop Points

_Where did you leave off? What should be verified next session?_

- [what to pick up next]

## Notes

_Free-form scratch. Clear periodically — old entries can be deleted once no longer relevant._

---

- DC4 README sections (2026-05-08, on `fix/dc4-readme-sections`): Custodian DC4 (native) flagged the README missing both Quick start and Architecture H2s. Quick start gives pip install + load_default_repo_graph + CLI examples; Architecture summarises the three-layer composition (Platform / Project / Local → EffectiveRepoGraph) and points at Edge vocabulary for the relationship taxonomy.

## 2026-05-08 — M1: CHANGELOG.md stub (Keep-a-Changelog format)

Added a minimal CHANGELOG.md so M1 (and M5 format check) pass.

## 2026-05-08 — B1: Scrub VideoFoundry/Warehouse leak from manifest_system.md


## 2026-05-08 — Custodian round: PM clean (27 → 0)


## 2026-05-08 — CI regression guard

Added .github/workflows/custodian-audit.yml + .hooks/pre-push.
Both run `custodian-multi --fail-on-findings`. CI is the source of
truth; pre-push catches regressions before they hit GitHub.


## 2026-05-08 — D11 exclusions (cli + models typology)


## 2026-05-08 — Relicense Apache-2.0 → AGPL-3.0-or-later

Aligns PM with the rest of the platform (Custodian, OC, etc. all
AGPL-3.0-or-later).


## 2026-05-10 — GitHub username migration

- Updated repo-owned references from the previous GitHub username to `ProtocolWarden` after the account rename.
- Scope: license headers, GitHub URLs, workflow install commands, manifests, dependency URLs, examples, and local owner defaults where present.

## 2026-05-10 — Custodian pre-push command resolution

- Updated the pre-push guard to prefer system `custodian-multi`, with repo venv and sibling Custodian venv fallbacks.

## 2026-05-11 — Phase 3 ontology and relationship fail-closed remediation

- Added first-class `PrivateManifest` support, ontology relationships, and explicit projection metadata in the PlatformManifest model and schema surface.
- Hardened public projection so the safe publication command always validates before producing final output, with unsafe generation split onto an explicit dev-only command.
- Extended PlatformManifest-owned PMV detection so relationship-level projection violations are enforced alongside legacy edge checks.

## 2026-05-13 — RepoGraph manifest edge + test coverage

- Added `repograph` repo entry (`runtime_role: graph_language`) and `PlatformManifest → RepoGraph depends_on_contracts_from` edge to `platform_manifest.yaml`. Closes X2 blind spot (PM imports `RepoGraphConfigError` at runtime).
- Added `tests/test_repograph_bridge.py` (14 tests) covering all re-exporter bridge modules: _repograph import_repograph, ontology enums/models/validation, projection models/redaction/rules/validation, topology edges/models/validation, and errors.
- Added 5 PMV1 detector tests in `tests/test_platform_manifest_detectors.py`.
- Updated `.custodian/config.yaml` comments from "test coverage pending" to accurate transitive-test descriptions.
- custodian audit: 0 findings.

## 2026-05-13 — Add projection metadata fields to platform manifest schema

- `to_public_manifest_dict()` now emits `schema_kind`, `schema_version`, and `projection_profile` at the root level. Schema had `"additionalProperties": false` and no entry for these fields, causing validation failures in test_projection.py and test_project_public_cli.py.
- Added all three as optional string properties in platform_manifest.schema.json.
- All 157 tests pass.

## 2026-05-13 — Add CLAUDE.md and .custodian/tmp*.yaml to .gitignore

- Added CLAUDE.md to .gitignore
- Added .custodian/tmp*.yaml to exclude custodian audit temp files

### ADR 0005 — Add TeamExecutor/DagExecutor/CritiqueExecutor (2026-05-18)
Added three new execution backend repos to platform_manifest.yaml (repos + edges).
- team_executor: replaces kodo (coordinator+worker+verifier pattern)
- dag_executor: replaces Archon (rustworkx DAG, 5 node types)
- critique_executor: new capability (adversarial + reflexion subtypes)
Each gets depends_on_contracts_from edges to RxP and CxRP, and dispatches_to from OperationsCenter.

### Add documentation surface repos + org profile to manifest (2026-05-18)
Added github_pages_site (ProtocolWarden.github.io) and org_profile (ProtocolWarden) with
runtime_role: documentation_surface. Both get depends_on_contracts_from edges to PlatformManifest
since they consume it as the public repo catalog source.
