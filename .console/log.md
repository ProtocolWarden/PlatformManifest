# Log
## 2026-06-04 — guard .context/ live session state from accidental commits
`.context/sessions/*/` and `.context/archived/*/` were untracked-but-unignored — held out
of the repo by convention only. A bare `git add -A` during today's bookkeeping staged 76k
machine lease files (caught in PR review, leak-scanned clean, commit rewritten before merge).
Now gitignored; config/engine/knowledge/templates + .gitkeeps stay tracked. Also untracked
three stale e2e test capsules from the 2026-05-27 spec validation (left on disk).

## 2026-06-04 — fleet reconciliation COMPLETE: last two private repos done
The two remaining light private repos are reconciled and enforcing; every repo in the
fleet (19 public + 3 private) now has a reconciled `.console/` with `reconcile_enforce: true`.
One of them was the private-manifest repo itself, which exposed a second CL gap (CL #21):
the self-name private signal (CL #20) can't fire there — its name is deliberately public-safe
— so `is_private_root()` (repo root == resolved private-manifest root) now also marks a repo
private in check/prune. Its prune also surfaced that B1 was flagging the archived private
history living on the private side BY DESIGN (39 findings incl. pre-existing archives);
sanctioned `archive/console/**` + `CHANGELOG.md` via the established privacy.exclude_paths
mechanism. Dashboard regenerated: 3 private repos tracked in aggregate.

## 2026-06-04 — private-repo reconciliation: the last heavy `.console` reconciled
The one repo the fleet reconciliation arc left untouched — a private downstream repo with a
6.8k-line `.console/log.md` — is now reconciled. Required an upstream ContextLifecycle change
first (CL #20): check/prune were public-repo-shaped (the scrub gate tripped on the repo's own
name; prune would have genericized the repo's own name inside its own tree). New rule: a repo
whose own name matches the scrub vocabulary IS a private repo → scrub gate + retained-content
scrub + CHANGELOG genericization skipped; DOC GAP gate unchanged. Then the standard recipe:
worksheet (43 items, 24 done/gated, 4 cross-repo routing rows, 9 open), 4 doc gaps backfilled
in the repo's own gate/design docs, prune --apply (log 6842→~140 lines, backlog 618→~300 with
completed [x] items moved out of active sections), archive to the private side (PrivateManifest
#12), `reconcile_enforce: true` (R1 active; R2 no-ops on private repos by design — verified in
Custodian's `_repo_is_public`). Mid-flight race: a session on another host pushed a gate rework
while we reconciled — rebased the prune over it, merged its new log/backlog entries on top of
the pruned files, and refreshed the just-written gate doc to match the reworked implementation.
Custodian full audit 0 findings; second --apply no-op. Dashboard regenerated (1 private repo
tracked in aggregate). The loop was not running locally before or during; nothing to resume.

## 2026-06-04 — Targeted warm-injection rollout: Custodian YES, OC skipped

Custodian became the second consumer of the CL injection engine (Custodian
#34): cl context init scaffold + a SLIM injection-only PreToolUse hook (no
ContextGuard; Custodian sessions were hook-free before), routes on the two CI
globs → ci-conventions.md copy (PM's copy canonical), .gitignore narrowed so
.claude/ ships. Verified match/no-match/flag-off + audit both ways.
OperationsCenter SKIPPED (operator decision): OC's .context/ was deliberately
removed — cognition is hosted by the anchoring manifest (hook resolves
REPO_ROOT from CL_ANCHOR; OC capsules live in the anchor's sessions/), so
repo-local injection conflicts with that recorded decision and anchor-side
routing can't match OC paths. OC is the deferred cross-repo-tier case;
revisit only if that tier is built. OC loops paused for the window and
resumed (8 lanes + controller ACTIVE, HEALTHY).

## 2026-06-04 — §7a re-evaluation: warm injection KEEP (empirical)

Re-ran the context-injection §7a gate against the live window. Engine healthy
(live run correct, exit 0); one routed edit occurred (PR #53 provision
scripts) with the injected conventions demonstrably followed; zero noise.
Phase-3 capture has produced 0 cold-store entries (nudge scans machine lease
records, not authored capsules — warn-only, left as-is); phase-5 trigger
provably runs, dry-run. Limiter is route coverage, not correctness: the
week's heaviest convention rework (B64 audit workflow, venv-guard) lived in
`.github/workflows/**` / `.custodian/*.yaml`, which no route matches.
Candidate follow-up: ci-conventions leaf doc + routes. Work order updated
(re-eval subsection + stale checkbox resolved). Follow-up BUILT same day:
`docs/inject/ci-conventions.md` routed on `.github/workflows/**` +
`.custodian/*.yaml` — distills the fleet-green/R2-rollout conventions (B64
step, venv-guard, fleet-coupled custodian@main, plugin_audit_keys,
fail-closed config). Both routes verified live; router tests 36/36.

## 2026-06-04 — FLEET GREEN: pre-existing red CI cleaned up on all 19 repos

Paused-loop batch (10 fixer agents + follow-ups), every workflow on every
public repo's main now green. Root causes: (1) venv-guard vs bare-pytest CI
mismatch (CoreRunner/SourceRegistry/RxP/SyncMechanism — workflows now create
.venv); (2) custodian-doctor's _KNOWN_AUDIT_KEYS missed reconcile_enforce
(fixed upstream in Custodian + plugin_audit_keys declared in 4 repos); (3)
missing SPDX headers (PD/SwitchBoard/SyncMechanism/Custodian); (4) stale
uv.lock pinning a renamed package (SwitchBoard); (5) OperatorConsole audit:
11 E701 + a CI-only cross-repo plumbing false positive; (6) Custodian
semantic-federation had NEVER run: dead *_FILE URL secret → B64 swap, then
renamed entrypoint, then missing ripgrep, then genuinely stale gate policy —
PUBLIC_REPOS/PUBLIC_REPO_CATALOG predated 5 public repos; lists synced to the
18-repo set, this repo's audit workflow swapped to the canonical
GITHUB_ENV pattern (was reconstructing a baked instance path — also dropped
from .custodian config; fail-closed verified), DAGExecutor/TeamExecutor gained
require_boundary_artifact, github.io dropped archival frontmatter. Federated
gate: exit 0, no findings. SyncMechanism operator WIP committed (approved) +
headers + headless pystray dummy backend.

## 2026-06-04 — Phase 6 closed as not-needed (operator decision)

Operator ruled: the private-manifest repo's *name* is not secret — only its
*contents* are, and those are already scrub-target-enforced. A lexical ban on
the instance name was therefore never needed (and was incoherent anyway: the
name collides with the public manifest-type vocabulary). The generalization
effort is COMPLETE: the guarantee is architectural (all bindings resolve the
role by discovery). Future project private-manifests with genuinely secret
names go into the boundary artifact's forbidden_names instead. Design doc
status updated.

## 2026-06-04 — Private-manifest role generalization EXECUTED (phases 1–5)

Executed the role-generalization design in a paused-loop window:
`repograph.resolve_private_manifest()` shared resolver (+5 tests), all 22
repos' pre-push hooks dropped the literal instance candidate (globs verified
to resolve the same artifact), provisioning scripts
(clone-repos/provision-machine/run_with_boundary) discover the
private-manifest root by the manifest-type filename or $PRIVATE_MANIFEST_DIR,
a downstream deployment repo's custodian config dropped its baked artifact
path (fail-closed verified), fixtures/docstrings/fix-hints generalized, ~80
doc instance refs fleet-wide rewritten to role phrasing. Phase 6 (lexical
scrub-target enforcement) BLOCKED: the instance repo is named identically to
the manifest-type vocabulary (ontology class/schema title) — needs an
operator decision (rename the instance) or stands on architectural
enforcement (no binding references the instance). Design doc §7 has the
execution record.

## 2026-06-04 — R2-in-CI complete fleet-wide + B64 rotation script

Closed the last R2-in-CI gap: added the canonical custodian-audit workflow
(B64 boundary-artifact materialization) to the 6 repos that lacked one
(ContextLifecycle #18, ProtocolWarden #6, ProtocolWarden.github.io #12,
RepoGraph #4, SyncMechanism #3, TeamExecutor #7 — TeamExecutor's misnamed
ruff/pytest "custodian-audit" renamed to ci.yml + 13 pre-existing ruff errors
fixed) and set their B64 secrets. All 6 new audit jobs verified green on
runners. All 19 public repos now enforce R2 in CI. Also modernized
`scripts/bootstrap-boundary-secrets.sh` to set/rotate the
REPOGRAPH_BOUNDARY_ARTIFACT_B64 content secret across all 19 repos in one
command (org-level secrets are impossible — the owner is a User account,
not an org; this script IS the consolidation story).

## 2026-06-04 — Design doc: private-manifest role generalization (#3)

Wrote `docs/architecture/private-manifest-role-generalization.md` — the design for
generalizing the hardcoded `PrivateManifest` instance (~244 refs, ~123 functional)
to a discovered private-manifest *role* (N project private-manifests), keeping the
`private_manifest.yaml` type as public vocabulary. Reuses CL's proven env-free
RepoGraph discovery; staged 6-phase migration with per-repo boundary-verification
because the refs ARE the boundary-enforcement plumbing (regression-critical).
Execution deferred as its own focused effort (not a tail-end add to the
reconciliation arc). Closes #3 as a design deliverable.

## 2026-06-04 — Generate the reconciliation status dashboard (#2)

Added `docs/architecture/console-reconciliation-status.md`, generated by
`cl reconcile index` (enhanced in CL #16 to list enforce-only public repos so it
covers the whole fleet): 4 prune-worksheet repos itemized (Custodian,
OperationsCenter, OperatorConsole, PlatformManifest) + 15 enforce-only/clean
public repos + 0 private (private repos stage inside themselves). Closes the
original "group them all somewhere" ask. Regenerate with the same command; do not
hand-edit.

## 2026-06-04 — `.console/` reconciliation (full: prune + scrub + enforce)

Ran the full `.console/` reconciliation pass per console-reconciliation-spec.md.
Authored `.console/reconcile.yaml` (untracked, gitignored) classifying every
completed work thread in the 477-line log as `done` + owner + existing doc[]
paths, with the 4 cross-repo layers (Phase 4 hot-trim → OperatorConsole, R1/R2
→ Custodian, `cl reconcile` → ContextLifecycle, archive → PrivateManifest) as
routing rows (listed, not gated). `cl reconcile check` GREEN, then `prune
--apply`: completed history moved to the private archive
(`PrivateManifest/archive/console/PlatformManifest/{log,backlog}-2026-06-04.md`),
tracked log trimmed 477 → ~30 lines + archive pointer, CHANGELOG appended,
retained content auto-genericized (scrub-target private names → "a private
downstream repo"). Second `--apply` is a no-op (md5 unchanged). Enabled the
opt-in `audit.reconcile_enforce: true` in `.custodian/config.yaml` now that the
tracked tree is leak-clean. Verified: `git grep` for the boundary-artifact
private identifiers (detector-ID forms excluded by word boundary) is empty
across all tracked files; 272 tests pass.

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

- DC4 README sections (2026-05-08, on `fix/dc4-readme-sections`): Custodian DC4 (native) flagged the README missing both Quick start and Architecture H2s. Quick start gives pip install + load_default_repo_graph + CLI examples; Architecture summarises the three-layer composition (Platform / Project / Local → EffectiveRepoGraph) and points at Edge vocabulary for the relationship taxonomy.

## 2026-05-08 — M1: CHANGELOG.md stub (Keep-a-Changelog format)

Added a minimal CHANGELOG.md so M1 (and M5 format check) pass.

## 2026-05-08 — D11 exclusions (cli + models typology)


## Archived

_Archived completed history → `/home/dev/Documents/GitHub/PrivateManifest/archive/console/PlatformManifest/log-2026-06-04.md`_

