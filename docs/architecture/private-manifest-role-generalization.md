# Private-manifest role generalization — design

> **Status:** PHASES 1–5 EXECUTED (2026-06-04). Phase 6 (lexical enforcement)
> is **blocked by design reality**: the repo *instance* is named identically to
> the manifest *type* vocabulary (`PrivateManifest` is also the public ontology
> class in RepoGraph/PlatformManifest and the schema title), so the instance
> name cannot become a scrub target without banning legitimate public API
> vocabulary. Lexical enforcement requires either renaming the private repo
> instance to a non-type name (operator decision) or accepting architectural
> (non-lexical) enforcement: every *binding* is now by role discovery, and the
> remaining literal occurrences are type vocabulary, sanctioned `.console/`
> history, or this document. Shared resolver:
> `repograph.resolve_private_manifest()`.
> Related: [console-reconciliation.md](./console-reconciliation.md),
> [visibility_boundary.md](./visibility_boundary.md),
> `PlatformDeployment/docs/architecture/adr/0003-boundary-artifact-tenancy-model.md`.

## 1. Problem

The platform hardcodes **`PrivateManifest`** (a specific repo *instance*) in ~244
references across public repos. ~123 are functional/load-bearing:

- ~19 `.hooks/pre-push` (boundary-artifact auto-discovery candidate path)
- provisioning: `provision-machine.sh`, `clone-repos.sh`, `bootstrap-boundary-secrets.sh`
- CI: `custodian-audit.yml` boundary-artifact materialization
- source: `RepoGraph/.../registry.py`, `platform_manifest/__init__.py` `__all__`,
  `Custodian/.../repograph_governance_gate.py` fix-hint strings
- tests: RepoGraph/Custodian/PlatformDeployment governance fixtures
  (`source_graph_id="PrivateManifest"`)
- ~96 doc references

But **`PrivateManifest` is one instance of a manifest *type***. The platform will
host **other project-specific private-manifest repos** (one private manifest per
project/ecosystem). Hardcoding a single instance everywhere is an architecture
smell: the tooling should reference the private-manifest **role** for the active
ecosystem, discovered at runtime — not a baked-in repo name.

## 2. Goal & scope

**Reference the private-manifest role by discovery, never a baked-in instance name.**

Critical scope distinction:

- **KEEP** `private_manifest.yaml` — this is the manifest *type* filename (public
  schema vocabulary, like `package.json`). RepoGraph discovers manifests by it.
  Renaming the type is a breaking schema change across RepoGraph + every manifest
  and is **out of scope**.
- **KEEP** the generic archetype phrasing ("a private manifest", "the private
  superset") in prose.
- **GENERALIZE** only the proper-noun *instance* `PrivateManifest` → resolved via
  role/discovery. Banning the literal instance name from public tracked files then
  falls out for free as a *side effect* of doing the architecture right (it is not
  the goal in itself).

Once generalized, `N` project private-manifests are supported: each public repo
resolves *its* ecosystem's private manifest, not a global singleton.

## 3. Design

The discovery mechanism already exists and is proven — `cl reconcile` resolves the
private manifest env-free via the RepoGraph registry (CL #14):

1. **Resolution order (the canonical resolver):**
   `$PRIVATE_MANIFEST_DIR` (explicit) → RepoGraph registry: the registered manifest
   repo whose discovered YAML is a `private_manifest*` (basename match, never a
   repo-name match) for the active ecosystem. Promote CL's
   `reconcile.privacy._discover_via_repograph` into a shared, public RepoGraph API
   (e.g. `repograph.resolve_private_manifest(ecosystem=…)`).

2. **Pre-push hooks (~19):** drop the literal `*/PrivateManifest/dist/...` candidate;
   the generic `*/dist/boundary_disclosure_artifact.json` glob + `$REPOGRAPH_BOUNDARY_ARTIFACT_FILE`
   already cover it. Reword the exporter help text off the instance name.

3. **Provisioning:** discover the private-manifest repo by scanning registered
   manifest roots for `*/data/private_manifest.yaml` (the type), or read the repo
   name from an **untracked** machine config / the existing secrets script — never a
   literal in a tracked script.

4. **CI:** already solved by the reconciliation work — the boundary artifact ships
   as the `REPOGRAPH_BOUNDARY_ARTIFACT_B64` content secret + materialization step;
   no repo name in any workflow.

5. **Source:** replace the `platform_manifest.__all__` literal + RepoGraph/Custodian
   fix-hint strings with the role concept / a `RepoType.PRIVATE_MANIFEST` archetype.

6. **Tests:** replace fixture `source_graph_id="PrivateManifest"` with a generic id
   (e.g. `"private-manifest-fixture"`), provided production code never matches the
   literal (it must not — that's part of the change).

7. **Docs (~96):** rewrite instance references to the role/archetype.

## 4. Migration phases (staged, low-risk)

1. **Shared resolver** in RepoGraph (promote the CL discovery) + tests. No behaviour
   change yet — additive.
2. **Hooks + CI** switch to the resolver/glob (already mostly there). Verify boundary
   enforcement still fires on every repo (the B-class + R2 must stay green/red exactly
   as before — this is the regression-critical step).
3. **Provisioning** switch to discovery/untracked-config.
4. **Source + tests** swap literals → role/archetype; run the full governance suite.
5. **Docs** sweep.
6. **Enforcement:** add the instance name to the scrub-target set so it can never
   re-enter public tracked files. Only after 1–5 are green.

## 5. Risks

- **Regression-critical:** these references *are* the boundary-enforcement plumbing.
  A wrong move silently disables B1/B2/R2 on some repos. Each phase must verify the
  boundary still fails-closed exactly as before (golden-test the artifact resolution
  per repo).
- Multi-ecosystem resolution (`N` private manifests) needs an "active ecosystem"
  signal per repo (the anchoring manifest) — RepoGraph's repo→owner map likely
  supplies it; confirm before relying on it.
- Partly self-undermining if rushed: provisioning still has to *locate* the repo, so
  "no instance name anywhere" requires the untracked-config indirection to be solid.

## 6. Why deferred

This is a fleet-wide change to load-bearing security plumbing — it warrants its own
focused effort (ideally a paused-loop window, phase-by-phase with per-repo boundary
verification), not a tail-end addition to the reconciliation work. The reconciliation
goal (close the leak, enforce R1/R2) is complete and independent of this; this
generalization is the *next* boundary-architecture project.

## 7. Execution record (2026-06-04)

Executed in a paused-loop window, per the staged plan:

1. **Shared resolver** — `repograph.resolve_private_manifest()` added to the
   RepoGraph registry module (`$PRIVATE_MANIFEST_DIR` override, else registry
   discovery by the `private_manifest*` type filename), with tests.
   ContextLifecycle's `_discover_via_repograph` now prefers it, keeping its
   inline discovery as a fallback for older RepoGraph installs.
2. **Hooks** — every repo's `.hooks/pre-push` dropped the literal instance
   candidate path; the generic `*/dist/` + `*/policy/` globs resolve the same
   artifact (verified). CI was already role-free (B64 content secret).
3. **Provisioning** — `clone-repos.sh` / `provision-machine.sh` /
   `run_with_boundary.sh` (a downstream deployment repo) resolve the
   private-manifest root via `$PRIVATE_MANIFEST_DIR` or a workspace scan for
   the manifest-type filename. PlatformDeployment's `.custodian/config.yaml`
   dropped its baked artifact path; absence still fails closed via its
   required-artifact privacy setting (verified exit 1 without the env).
4. **Source + tests** — governance-gate fix-hints and docstrings use role
   phrasing; test fixtures' `source_graph_id` swapped to generic ids (verified:
   no production code matches the literal).
5. **Docs** — ~80 instance refs across the fleet rewritten to role phrasing /
   path placeholders; manifest-*type* vocabulary (ontology class, schema title,
   layered-stack diagrams) deliberately kept.
6. **Enforcement** — BLOCKED, see Status note above (instance name ==
   type-class name). Resolution options: rename the private repo instance,
   or rest on the architectural guarantee that no binding references the
   instance.

Boundary regression checks per phase: audits clean *with* the artifact and
fail-closed *without* it, on every touched repo.
