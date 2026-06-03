# Log
## 2026-06-03 — Add cross-machine resume section to the work order

Added a "▶ Resume here" block at the top of
`docs/architecture/context-injection-work-order.md` so the spec build can be
picked up on another machine via `git pull`: current state (Phase 0–2 merged to
main, engine dark), how to verify, the §7a gate fork (wire+gate before any Phase
3–5), and the gotchas that bit us (OC bot auto-force-pushes branches; main is
unprotected; CI needs the boundary-artifact secret). Whitelisted `main` in
`.custodian/config.yaml` known_values (K2: branch name, not a src enum).

## 2026-06-03 — Make CI green (5 pre-existing failures, none from recent work)

CI had been red on `main` and PR #39 merged over it. Root-caused and fixed all
five checks on branch `fix/ci-health`:
- ruff F401 in `errors.py` (RepoGraph re-export) → added `__all__`.
- `tests/test_visibility_scope.py` missing SPDX header → added it.
- pytest `conftest.py` venv-guard rejected CI's interpreter → set
  `CUSTODIAN_SKIP_VENV_GUARD=1` in the test job (its documented opt-out).
- `repograph` never installed in CI → pip-install from public git in
  test/validate jobs.
- audit boundary-artifact secret held a machine-local *path* (impossible on a
  runner) → switched to base64 *content* secret `REPOGRAPH_BOUNDARY_ARTIFACT_B64`,
  decoded to a runner file. **Requires the operator to set that secret.**

Local: ruff clean, 189 tests pass, both workflows parse, base64 round-trip OK.

Follow-ups after first CI run (down to 1 failure from many):
- `custodian` also wasn't installed in the test job (imported by
  `custodian_native`) → added it from public git.
- `test_no_validate_is_not_allowed_on_safe_command` failed only under CI's
  `FORCE_COLOR`: rich interleaves ANSI codes inside the option name, breaking a
  raw `"--no-validate" in output` check. Reproduced on a pyenv 3.11.9 venv with
  `FORCE_COLOR=1`. Fixed by stripping ANSI before the assertion (`_strip_ansi`).
- Audit never re-ran (pull_request[synchronize] doesn't fire in this repo) →
  trigger custodian-audit on `push: ["**"]` like ci.yml.
- Audit then surfaced 3 MED: custodian reads the boundary path from
  `.custodian/config.yaml` (`../PrivateManifest/dist/...`), NOT an env var →
  materialize the base64 secret to that exact path; and set `core.hooksPath`
  in CI to clear W2. All six checks green.

## 2026-06-03 — Verify PreToolUse protocol + draft Phase 2-wire (still dark)

Verified the Claude Code PreToolUse context-injection protocol and drafted the
hook wire WITHOUT touching the live hook:
- Protocol: inject via stdout JSON parsed only on exit 0 —
  `{"hookSpecificOutput":{"hookEventName":"PreToolUse","additionalContext":"…"}}`;
  omit `permissionDecision` to add context without altering permission flow;
  `exit 2` blocks; 10k-char cap.
- **Spec §4 fixed:** PostToolUse *does* support `additionalContext` (spec had
  said it doesn't). Rewrote the bullet: both pre/post support it on exit 0; the
  warn-only logger stays purely passive (exit 0, no output). Choice unchanged —
  PreToolUse still right (inject before the write).
- **`jq` absent on dev box** — live hook + draft both use the `python3` fallback.
- Draft parked at `docs/architecture/phase2-wire-draft.sh`, validated end-to-end
  against the real engine (abs→relative path strip, all-matches, valid JSON,
  empty-on-no-match). Live `pre_tool_use.sh` deliberately untouched (editing it
  mid-session is the lockout risk). Work order Phase 2-wire updated.

## 2026-06-02 — Implement context-injection engine (Phase 0–2, ships DARK)

Work order: `docs/architecture/context-injection-work-order.md`. Implemented the
warm-injection prototype for the spec, scoped to project tier and shipped dark
(no behaviour change):
- **Router engine** `.context/.engine/route.py` — all-matches glob routing,
  injection budget + priority, `engine_compat:` version-degradation (no injection
  on mismatch), `## Inject`-only extraction. Pure stdlib + PyYAML; in `__main__`
  it never raises and never exits non-zero, so it cannot block a tool call when
  later wired into a hook.
- **`.context/routes.yaml`** (5 real PM domains) + 5 **leaf docs** under
  `docs/inject/` carrying genuine, code-grounded conventions (loader fail-closed
  visibility, projection validate-before-emit, visibility boundary, schema
  `additionalProperties:false` gotcha, provisioning idempotency/exit-codes).
- **`config.yaml` `injection.enabled: false`** — engine is not invoked from any
  hook yet; `pre_tool_use.sh` is untouched (avoids the parole-officer lockout).
  Live wiring is the next, gated step (needs the PreToolUse additionalContext
  protocol verified).
- **`.context/knowledge/`** scaffold for the (gated) cold tier.
- **Tests** `tests/test_context_router.py` (21) — routing/budget/version/extraction
  + an anti-staleness guard importing the src symbols the leaf docs name (also
  satisfies T8 honestly). Full suite 189 pass.

Custodian-clean: only added a `docs/inject/**` orphan exclusion (injected
fragments aren't human doc-tree), same rationale as verification artifacts.

## 2026-06-02 — Draft spec: tiered memory & context injection

Added `docs/architecture/context-injection-spec.md` — design checkpoint for the
next-gen context system (DRAFT, not approved for build). Captures a long design
session that started from the Patterson hook-injection article and the
realization that `.context/` is enforcement-only with no knowledge store.

Key decisions reached (recorded so future-PM sees the reasoning, not just the
conclusion):
- **Four-tier memory** by lifespan/cost: hot (always-loaded anchor) / warm
  (`docs/inject/*.md`, pushed by a router on matching edit) / cold
  (`.context/knowledge/`, surfaced on match) / ephemeral (session capsule).
  Injection timing — right doc right before the edit — is the core value, not
  volume.
- **Promotion gate is consequence-veto + usage-decay-with-pinning**, NOT
  vote-counting. Retired self-reported confidence, `cited_sessions`, and
  change-based TTL after adversarial passes showed each was agent-gameable,
  injection-contaminated, or anti-correlated with validation.
- **Cross-repo is publish-down, not bubble-up**: authority flows from the
  manifest that OWNS a contract (oracle = its schema/tests), downward to
  anchorers; consumer discoveries are reports into the owner's cold store, never
  unsupervised global writes. Design-locked, build-deferred.
- **Capture/consolidate intake has forcing functions** (Stop-hook capture +
  automatic campaign-close trigger) because the 54 orphaned session dirs prove
  manual lifecycle commands don't get run.
- **Build is gated** after phase 2 (warm injection): prove it helps before
  building the cold/consolidation pipeline. Store boundary explicit — cold is
  repo-committed `.context/knowledge/`; `~/.claude` operator memory is untouched.

Engine lives in the CL repo (provisioned), not `.context/`. Open questions
parked in §9 (forcing-function hardness, consequence attribution, owned-contract
definition). Linked from `docs/README.md` (Design drafts) and made Custodian-clean
(K1 phantom-symbol avoided via the existing `engine_compat:` colon convention; no
config exclusions added).

## 2026-05-28 — Document the ContextLifecycle anchoring architecture

Added docs/architecture/contextlifecycle-anchoring.md — the cross-cutting design
behind session anchoring: CL_HOME (machine state) vs CL_ANCHOR (session state),
the canonical cl resolution order (CL_HOME → settings.json → PATH) and why
`source ~/.bashrc` fails in non-interactive shells, where each consumer resolves
cl (OC panes bake the path; OC + tenant loop controllers use _resolve_command
with the settings.json fallback; committed hooks delegate to `cl hook`; provisioning
records CL_HOME), and the hook exit-code enforcement model (2=block, 1=non-block)
that makes a fresh clone bootstrap-safe. Linked from the README.

## 2026-05-28 — Track OperatorConsole in hook-health

OperatorConsole now carries committed ContextGuard hooks (previously had none).
Added it to COMMITTED_HOOK_REPOS so the hook-health check verifies its hooks are
present + executable on every provision.

## 2026-05-28 — Provisioning: orchestrator, venv refresh, hook-health, doc

Closed gaps from a self-provision design review:
- **provision.sh** (new): single entrypoint chaining clone-repos → provision-machine
  in the only order that works (CL+RG must clone before provision-machine requires
  them). Flags pass through. README documents the sequence + the manual
  boundary-secrets follow-up.
- **Stale venvs**: `_ensure_venv` now always re-runs `pip install -e` so a
  re-provision after a dependency-changing `git pull` is picked up (was: only
  built when the venv was missing).
- **Hook drift**: added a warn-only "Hook health" step verifying every managed
  repo's `pre_tool_use.sh` is present + executable — surfaces drift the install
  step's "already present, skipping" path hid. Corrected the stale comment that
  claimed OperatorConsole carries custom hooks (it carries none; it's the
  launcher TUI). Added COMMITTED_HOOK_REPOS so committed-hook repos are verified.

Not changed: the systemd VF-loop unit lacking CL_HOME — it's a temporary local
watcher, out of scope.

## 2026-05-27 — Fix B1: remove hardcoded private names from provision/clone scripts

Dynamic discovery replaces hardcoded private repo names — private manifest YAMLs discovered via `find` at runtime, canonical names parsed by Python. No private names appear in this public repo's source.

## 2026-05-27 — Populate RepoGraph registry; wire boundary artifact to custodian

Registered PlatformManifest and PrivateManifest in the machine RepoGraph registry (`~/.config/repograph/manifests.yaml`). Added `CL_HOME`/`PATH` setup to `~/.bashrc` so bare `cl` is available to loop controllers and bootstrap scripts. Added `boundary_artifact_file` to `.custodian/config.yaml` so B2 (require_boundary_artifact) resolves correctly against PrivateManifest's generated artifact. SyncControl is private and belongs to PrivateManifest (not here).

## 2026-05-22 — Fix bundled-validation: add RepoContextLifecycleFlags to schema

Pre-existing `test_bundled_validates_clean` failure: PM YAML had `context_lifecycle:` blocks per repo (added 2026-05-21 + extended in ADR 0002 P6), but `PublicRepoNode` / `RepoNode` schemas declared `additionalProperties: false` without naming the field. Added `RepoContextLifecycleFlags` $def to both `platform_manifest.schema.json` and `private_manifest.schema.json` with the full set of flags currently in use (participates, cognition_host, manifest_scope_declared, shim_only, dispatcher_integration, cli_provider, schema_owner, contextguard, workspace_capsules). All 168 tests now pass.


## 2026-05-22 — P6: declare cognition_host participation metadata

Branch: `feat/p6-cleanup`. Phase 6 of work order `PlatformDeployment/docs/architecture/adr/0002-work-order-manifest-cognition.md`.

Updated `src/platform_manifest/data/platform_manifest.yaml` `context_lifecycle` blocks to reflect the post-P5 world:
- PlatformManifest: `cognition_host: true`, `manifest_scope_declared: true` (it now hosts `.context/sessions/` for public-scope work).
- OperationsCenter: `cognition_host: false`, `shim_only: true`, `dispatcher_integration: true` (CL shim in `.claude/hooks/`; `cl_dispatch_wrap` around adapter calls per P4).
- TeamExecutor / DAGExecutor / CritiqueExecutor: `cognition_host: false`, `shim_only: true` (9-line shim only, no local `.context/` per P5).
- ContextLifecycle: added `cli_provider: true` (ships `cl` CLI + hydrate/capture/peek API per P1).

Public-manifest metadata is now an honest catalog of who actually hosts CL state vs who only carries a shim.

## 2026-05-22 — Link context-layout.md from docs README (fix DC7)

Custodian flagged `docs/context-layout.md` (added in P3) as orphan — not linked from any tracked doc. Added link from `docs/README.md` under a new "Cognition Hosting" section.

## 2026-05-22 — P3: become cognition host (`.context/` skeleton)

Branch: `feat/p3-context-host`.

Phase 3 of work order `PlatformDeployment/docs/architecture/adr/0002-work-order-manifest-cognition.md`. PM now hosts durable CL state for any session anchored here (`CL_ANCHOR=<PM>`). Consumer repos (OC, executors) stop carrying their own `.context/`.

Added:
- `.context/sessions/` and `.context/archived/` (runtime session dirs land under sessions/; `cl session end` moves them to archived/).
- `.context/templates/{investigation_capsule,worker_handoff,loop_checkpoint}.template.yaml` — copied from OC and stripped of OC-specific text (no `repo: "OperationsCenter"` defaults, no OC paths in `allowed_paths`). `loop_checkpoint` renamed from `watchdog_checkpoint` since it's the generic name.
- `.context/config.yaml` — manifest-wide CL config. Guard flags only (`require_capsule: false`, `enforce_lease: true`, capsule/checkpoint/handoff paths relative to session subdir). Explicitly does NOT carry consumer-repo operational config (worker definitions, watchdog cycle) — those stay in consumer `.console/`.
- `docs/context-layout.md` — explains the layout and the public-scope contract for what PM can host (per RepoGraph clause 1 + 2; cannot host private-owned repo cognition).

Companion changes:
- PrivM: same skeleton on its own `feat/p3-context-host` branch.
- OC: `.context/` removed on `feat/p3-remove-local-context`; OC's worker config moved to `.console/workers.yaml`, runtime schedule file moved to `.console/loop_schedule.json`; watchdog controller + session prompt updated to the new paths.

Not committed yet — staged for parent review.

## 2026-05-22 — P2: add visibility_scope + also_hosts top-level fields

Branch: `feat/p2-add-visibility-scope`.

- `src/platform_manifest/data/platform_manifest.yaml`: declared
  `visibility_scope: public` and `also_hosts: []` at top level.
- `src/platform_manifest/schemas/platform_manifest.schema.json` +
  `private_manifest.schema.json`: added `visibility_scope` and `also_hosts`
  properties (without unsetting `additionalProperties: false`).
- `src/platform_manifest/loader.py`: new `parse_visibility_scope()` and
  `parse_also_hosts()` helpers, exposed from the loader module. Backward-compat
  rule: when `visibility_scope` is absent, derive `public` only if every
  `repos[*].visibility` is `public`; otherwise raise (forces explicit
  declaration for any mixed-scope manifest).
- New `tests/test_visibility_scope.py` (11 tests) covers helper behavior +
  asserts the bundled YAML still loads after the schema change. PM suite:
  167 pass / 1 pre-existing failure (unrelated: `context_lifecycle` repo
  field rejected by current PublicRepoNode schema).

## 2026-05-22 — "Manifest" locked in as a first-class repo type

Design session in CL (see `ContextLifecycle/.console/log.md` 2026-05-22 entry for the full walkthrough). Recording the manifest-specific outcomes here so future-PM sees them.

**Repo type — manifest:** a manifest is a repo whose job is to (1) declare what's in an ecosystem, (2) host that ecosystem's cognition state under `.context/`, and (3) anchor sessions that operate on it. PM and PrivateManifest are the current instances; the pattern is extensible.

**Visibility scope:** PM is `public`. PrivateManifest is `private` (superset — can host state involving public repos; PM cannot host state involving private repos).

**Info-flow rule (general, not cognition-specific):** a manifest can host state involving any repo at or below its visibility scope. Enforced by RepoGraph at write time. Applies to any state a manifest hosts, not just cognition.

**What this means for PM going forward:**
- PM gains a `.context/` directory as the cognition host for public-scope sessions (capsules, checkpoints, handoffs).
- PM becomes a session anchor — operators launch sessions via `cl session start PlatformManifest` (sets `CL_ANCHOR` env var). Hard error if anchor missing.
- Consumer repos (executors, etc.) carry only a 1-line shim hook; they no longer host their own `.context/` data.
- PM's existing repo-membership declarations become the source RepoGraph reads for visibility checks.

**Stop point:** PM doesn't need to change yet — implementation lands in CL first (CLI + shim). Once CL ships, add `.context/` skeleton here and update repo-membership schema for RepoGraph consumption.

## 2026-05-21 — Add CLP participation metadata to platform manifest

Added context_lifecycle participation metadata to OperationsCenter and
ContextLifecycle nodes. OC: participates=true, workspace_capsules=true,
contextguard=true. CLP: schema_owner=true, contextguard=true. PlatformManifest
describes capability/participation only — not live runtime state.

## 2026-05-21 — Add closing fence to console-context block

Added <!-- /console-context --> end marker so OperatorConsole only replaces its
managed block and leaves repo-owned content below it untouched.

## 2026-05-21 — Fix B1 boundary violation in platform_manifest.yaml

Removed VideoFoundry name from inline comment — Custodian B1 flags private repo names in
tracked public files. Replaced with generic "Private project consumers" phrasing.

## 2026-05-21 — Add Warehouse and ContextLifecycle to manifest

Added two repos missing from the public platform graph:
- Warehouse (context_staging) — already referenced in github.io catalog and org profile but absent from manifest
- ContextLifecycle (cognition_lifecycle) — new public repo; added OC→CLP depends_on_contracts_from edge
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

## 2026-05-23 — Add CritiqueExecutor→CoreRunner edge

- platform_manifest.yaml: declared dispatches_to edge CritiqueExecutor→CoreRunner (CE imports core_runner; clears custodian X2 in CritiqueExecutor).

## 2026-05-23 — Register SyncMechanism node

- platform_manifest.yaml: added SyncMechanism (public, runtime_role fleet_sync_mechanism) — the public Syncthing install/runtime mechanism extracted from the private fleet layer.

## 2026-05-27 — Add machine provisioning scripts

Added `scripts/provision-machine.sh` (idempotent: builds CL+RG venvs, wires CL_HOME in ~/.bashrc, registers manifests in RepoGraph, installs adapter hooks into repos missing them) and `scripts/clone-repos.sh` (clones all repos from platform_manifest.yaml via SSH, --with-private extends to PrivateManifest). Also installed ContextGuard full adapter into PlatformManifest itself (.claude/hooks/). OperatorConsole/setup.sh now calls provision-machine.sh as part of its flow.

## 2026-05-27 — Track today's CL session capsules

Three e2e-verification capsules from today's RepoGraph registry + CL integration work.

## 2026-05-27 — Fix provision: wire CL_HOME into ~/.claude/settings.json

provision-machine.sh step 3 now also writes CL_HOME into ~/.claude/settings.json env section. This makes CL_HOME available to Claude Code's process and its hook subprocesses, which don't source ~/.bashrc. CL_ANCHOR is still session-dynamic (set via eval "$(cl session start)" before launching).

## 2026-06-03 — Phase 2-wire: splice context-injection into the live hook (dark)

Spliced the validated `docs/architecture/phase2-wire-draft.sh` block into `.claude/hooks/pre_tool_use.sh` (between `# All checks passed` and the final `exit 0`; 338 → 381 lines) on branch `feat/phase2-wire-context-injection`. The block is gated on `injection.enabled` (still `false`) and wrapped so any failure is swallowed — it can never block a tool call. Because the hook governs the operator's own session, validated `bash -n` on a temp copy *before* the live swap, then copied the exact validated bytes in. Smoke-tested through the real hook with the flag toggled on+restored atomically: Write→`loader.py` emits valid PreToolUse `additionalContext` (944 chars, exit 0), Write→`README.md` (no route) emits nothing, flag-off is fully inert. Router tests 21/21. Flag deliberately left dark — flipping it is the §7a gate decision, not part of wiring. No controller handoff (operator-driven).

## 2026-06-03 — Prove-and-harden workflow on context-injection engine

Ran a dynamic verify→fix→prove workflow (28 agents) over the implemented engine+wire against the spec. 21 findings → 11 confirmed real defects, all fixed; router suite 21→36 cases, green. Engine fixes (.context/.engine/route.py): (1) silent budget truncation now reported (spec §3, select_docs_split returns kept+dropped); (2) target.lstrip("./") char-set bug → literal "./" prefix strip (dotfile targets like .github/** now route); (3) non-positive max_docs treated as uncapped, not a negative slice index; (4) shared-doc dedupe ranks by MIN priority across matching routes, not first-sight; (5) MISSING_DOC sentinel distinguishes broken-route (missing file) from empty ## Inject, and reports even when all matched docs unusable; (6) load_routes wraps int() of budget/priority in try/except → fail-closed (uncapped / default 100) instead of raising; (7) interior **/ glob requires surrounding separators (a/**/b matches a/b, a/x/b, not ab). Never-raises and never-block contracts preserved; flag still dark. Also fixed spec §4 PostToolUse-exit-2 wording and stale test counts in the work-order.
