# Log
## 2026-06-16 — Decision 1 gate built: Direction-A CAP1 CI (capability plane)

Added `.github/workflows/capability-refs.yml` — the Direction-A enforcement venue
from the resolved decisions. On a `capabilities.yaml` change it checks out the 3
bounded owning repos (Custodian, OperationsCenter, ContextLifecycle) alongside the
PR's registry and runs `custodian-multi --only CAP1`, so a registry edit pointing
a ref at missing/renamed owner code fails at the repo where it was authored —
closing CAP1's single-repo-CI blind spot. Proven locally: clean pass + negative
control (break board_unblock's ref → OperationsCenter CAP1 fails). Direction-B
(owner renames a symbol) stays covered by that repo's own pre-push. Also ran
`cl reconcile prune --apply` (log 399→32, history archived to the private side) —
the proper archive+trim, replacing the inline trims I'd been doing.

## 2026-06-16 — Resolved the 3 capability-plane open decisions (adversarial)

Code-grounded adversarial analysis per decision; recorded in
`capability-plane-completion-spec.md`. (1) CAP1 venue → SPLIT GATE: owning-repo
pre-push already covers code-side breaks; add a PM-CI bounded multi-repo checkout
for registry-side breaks (the real gap, prerequisite for population). (2) CAP2
coverage detector → DON'T BUILD (3-entry registry, ~0 omissions; revisit advisory
past ~15–20). (3) artifact registry / CAP3 produces → DEFER (zero consumers).

## Recent Decisions

_Log significant choices here so they survive context resets._

| Decision | Rationale | Date |
|----------|-----------|------|
| Promote multi-repo composition to first-class `WorkScopeManifest` (manifest_kind: work_scope). v0.9.0 ships transitional support; project+includes still loads with DeprecationWarning. v1.0.0 will hard-fail. | Overloading `manifest_kind: project` for shells blurred the trust posture — a shell composes, a project describes. Distinct kind + schema + provenance (Source.WORK_SCOPE) prevents semantic drift and enables strict slot validation in OC settings. | 2026-05-08 |
| Ship worked examples in `examples/{single_project,work_scope}/` and validate them in CI. README + OC operator docs migrated to v0.9 vocabulary. | An operator authoring their first manifest needs a runnable starting point that's kept fresh by CI, not a copy-paste blob in markdown that rots. The examples pin v0.9 platform_manifest constraints, exercise both manifest kinds, and the CI step `validate-examples` ensures schema/loader changes can't silently break authoring guidance. | 2026-05-08 |
| Cut PM v1.0.0: hard-fail `manifest_kind: project` with `includes:` (R4). | Scan of all five sibling repos found zero authored legacy shells, so the gating criterion was already satisfied. Leaving the deprecation branch around just preserves ambiguity for future authors. v1.0.0 removes `includes` from the project schema (schema rejects at the field-validation layer), drops the deprecation warning in `_apply_project` and replaces it with an explicit migration-hint `RepoGraphConfigError` (catches direct loader callers that bypass schema), deletes `test_includes.py` (project-of-project recursion is no longer reachable; collision/composition rules are covered by `test_work_scope.py`), bumps example version_constraints to `>=1.0,<2.0`. | 2026-05-08 |
| Scrub Warehouse-as-asset-producer framing from PM artifacts. | The R7.2/R7.3 motivating example was wrong-semantics — Warehouse is developer/operator tooling (repo chunking, LLM context extraction), NOT a runtime artifact provider. a private downstream repo doesn't operationally consume Warehouse-produced artifacts. Audit confirmed the bad edge was never in any committed `topology/project_manifest.yaml` (a private downstream repo still pins `>=0.3,<1.0`, edge absent), but the framing fossilized in `models.py` docstring + `tests/test_repo_graph.py` node labels + `docs/verification/manifest_system.md`. Synthetic test labels switched to `GenericApi/GenericWorker/AssetPublisher`; docstring + verification doc reframed around generic "asset publisher"; verification doc carries an explicit retraction note. Edge type `BUNDLES_ASSETS_FROM` itself stands — keep until a real producer/consumer asset relationship surfaces. Mechanism stays correct; semantic interpretation corrected before the graph vocabulary fossilized around it. | 2026-05-08 |
| Add no-implicit-discovery invariant tests. | DoD audit caught that the verification spec's "loader does not scan sibling directories / does not glob" assertion was not explicitly covered. New `TestNoImplicitDiscovery` (2 cases) places sibling `decoy.yaml` + `topology/project_manifest.yaml`-named decoys alongside an explicitly-included manifest and proves they are NOT pulled in. Defense-in-depth against future "but it'd be convenient if it auto-discovered..." regression. | 2026-05-08 |

## Notes

_Free-form scratch. Clear periodically — old entries can be deleted once no longer relevant._

---

## Archived

_Archived completed history → `/home/dev/Documents/GitHub/PrivateManifest/archive/console/PlatformManifest/log-2026-06-04.md`_

