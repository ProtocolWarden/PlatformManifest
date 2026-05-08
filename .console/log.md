# Log

_Chronological continuity log. Decisions, stop points, what changed and why._
_Not a task tracker — that's backlog.md. Keep entries concise and dated._

## Recent Decisions

_Log significant choices here so they survive context resets._

| Decision | Rationale | Date |
|----------|-----------|------|
| Promote multi-repo composition to first-class `WorkScopeManifest` (manifest_kind: work_scope). v0.9.0 ships transitional support; project+includes still loads with DeprecationWarning. v1.0.0 will hard-fail. | Overloading `manifest_kind: project` for shells blurred the trust posture — a shell composes, a project describes. Distinct kind + schema + provenance (Source.WORK_SCOPE) prevents semantic drift and enables strict slot validation in OC settings. | 2026-05-08 |
| Ship worked examples in `examples/{single_project,work_scope}/` and validate them in CI. README + OC operator docs migrated to v0.9 vocabulary. | An operator authoring their first manifest needs a runnable starting point that's kept fresh by CI, not a copy-paste blob in markdown that rots. The examples pin v0.9 platform_manifest constraints, exercise both manifest kinds, and the CI step `validate-examples` ensures schema/loader changes can't silently break authoring guidance. | 2026-05-08 |
| Cut PM v1.0.0: hard-fail `manifest_kind: project` with `includes:` (R4). | Scan of all five sibling repos found zero authored legacy shells, so the gating criterion was already satisfied. Leaving the deprecation branch around just preserves ambiguity for future authors. v1.0.0 removes `includes` from the project schema (schema rejects at the field-validation layer), drops the deprecation warning in `_apply_project` and replaces it with an explicit migration-hint `RepoGraphConfigError` (catches direct loader callers that bypass schema), deletes `test_includes.py` (project-of-project recursion is no longer reachable; collision/composition rules are covered by `test_work_scope.py`), bumps example version_constraints to `>=1.0,<2.0`. | 2026-05-08 |
| Add no-implicit-discovery invariant tests. | DoD audit caught that the verification spec's "loader does not scan sibling directories / does not glob" assertion was not explicitly covered. New `TestNoImplicitDiscovery` (2 cases) places sibling `decoy.yaml` + `topology/project_manifest.yaml`-named decoys alongside an explicitly-included manifest and proves they are NOT pulled in. Defense-in-depth against future "but it'd be convenient if it auto-discovered..." regression. | 2026-05-08 |

## Stop Points

_Where did you leave off? What should be verified next session?_

- [what to pick up next]

## Notes

_Free-form scratch. Clear periodically — old entries can be deleted once no longer relevant._

---

- DC4 README sections (2026-05-08, on `fix/dc4-readme-sections`): Custodian DC4 (native) flagged the README missing both Quick start and Architecture H2s. Quick start gives pip install + load_default_repo_graph + CLI examples; Architecture summarises the three-layer composition (Platform / Project / Local → EffectiveRepoGraph) and points at Edge vocabulary for the relationship taxonomy.
