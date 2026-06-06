# `.console/` Reconciliation — SPEC

Implementation spec derived from [console-reconciliation.md](./console-reconciliation.md).
Companion design holds rationale + the adversarial pass; this file is the
contract the implementation is built and verified against.

Invariants (must hold at every phase): **I1** consolidate-before-prune,
**I2** boundary (no scrub-target private identifiers — see §1 — in
public tracked files), **I3** prune = move + trim, never delete. `PrivateManifest`
is NOT a scrub target (separate deferred item).

---

## §1 Scrub-target vocabulary (shared)

A single source of truth for "public-leak names": the private-repo identifiers
(canonical + snake_case forms, plus their short aliases matched on word boundaries
so detector IDs are never tripped). The literal set is NOT enumerated in this
public doc (I2) — it is read from the boundary artifact's identifier list.
This set is distinct from `PrivateManifest` (not a scrub target).
Implementations MUST read it from that one source, never hardcode in multiple files.

**AC1:** changing the scrub set in one config location changes detection and
`cl reconcile` behavior everywhere; no second hardcoded copy.

## §2 Layer A — Custodian detectors

**Opt-in (rollout-safe):** R1 and R2 are gated behind `audit.reconcile_enforce`
(default **false**). Because CI installs `custodian@main`, a default-on detector
would fail every public repo's `--fail-on-findings` the moment it merged — before
those repos are reconciled. They ship dormant and a repo flips
`reconcile_enforce: true` only *after* it is reconciled (§6). Custodian dogfoods it.

### R1 (advisory) — `.console/` over budget
Fires when a tracked `.console/*.md` exceeds a configurable line budget
(`audit.r1_line_budget`, default 400). Severity LOW/advisory. One finding per file.

**AC2:** a 500-line `.console/log.md` yields exactly one R1; a 200-line one yields none;
disabling via config suppresses it.

### R2 (fail-closed) — scrub-target leak in public `.console/`
Fires when a scrub-target name (§1) appears in a tracked `.console/**` file of a
**public** repo (public = present in `platform_manifest.yaml`). This deliberately
overrides B1's default `.console/**` exclusion *for scrub-target names only*.
`PrivateManifest` and B1's normal names keep their existing exclusion behavior.

**AC3:** a public repo whose `.console/log.md` contains a scrub-target identifier
yields an R2 finding; the same file containing `PrivateManifest` does NOT;
`.console/` content with no scrub-target names is clean; a private repo is exempt.
**AC4:** R2 fires today on the known-leaking public repos (Custodian, OperationsCenter, …)
and is silent after their scrub.

### Registration + docs
R1/R2 registered in the appropriate Custodian detector builder; documented
in Custodian's detector-disposition matrix (docs/design/) as a new **R-class**.

## §3 Layer B — `cl reconcile` (ContextLifecycle)

New subcommand group `cl reconcile` (Typer), package
`src/context_lifecycle/reconcile/`.

### §3.1 Worksheet schema (`.console/reconcile.yaml`, untracked)
```yaml
schema: 1
repo: <RepoName>
items:
  - id: <kebab>            # unique within repo
    title: <str>
    status: done | partial | incomplete
    owner: <RepoName>      # defaults to repo; owner != repo ⇒ cross-repo
    doc: [<repo-relative path>, ...]   # durable design locations
```
Loader is fail-soft (malformed item → skipped with a warning, never raises).

### §3.2 `cl reconcile check` — the I1 gate (read-only)
Exit non-zero if any: (a) a `done` item whose documented-location list is empty,
or names a path that does not exist → **DOC GAP**; (b) any field contains a
scrub-target name (§1) — I2; otherwise 0.
Prints: DOC GAPs, cross-repo items (`owner != repo`) as routing suggestions,
and a clean/blocked summary. Never mutates.

**AC5:** a worksheet with a `done` item + empty `doc` exits non-zero naming that item;
filling `doc` with an existing path flips it to exit 0. **AC6:** a scrub-target name
in any field fails `check`. **AC7:** cross-repo items are listed, not gated.

### §3.3 `cl reconcile prune` — runs only when `check` is green
For each `done` item with `owner == repo`:
1. Move its source history (the matching `## ` log sections / completed backlog
   sections) → `<private-manifest-repo>/archive/console/<repo>/<file>-<cutoff>.md`
   (append; create dirs). Path resolved via `$PRIVATE_MANIFEST_DIR` or discovery
   (do NOT hardcode the repo name in CL source — I2 / [[private-manifest-generalization]]).
3. Trim the tracked source to: active sections (`In Progress`/`Up Next`/unrecognized)
   + most-recent-N log entries (default 10) + a one-line pointer to the archive.
4. Append a scrubbed one-line entry to the repo's `CHANGELOG.md` (public record of
   *what* shipped — names genericized).
Idempotent (re-run after green = no-op). Dry-run by default; `--apply` mutates.
Refuses to run if `check` is not green.

**AC8:** dry-run reports planned moves, mutates nothing (verified by checksum).
**AC9:** `--apply` on the Custodian pilot moves completed history to the private
archive, leaves active+recent in source, adds the pointer + CHANGELOG line, and a
second `--apply` is a no-op. **AC10:** after prune, `cl reconcile check` is still
green and Custodian's tracked `.console/` has zero scrub-target names (R2 clean).

### §3.4 `cl reconcile index` — generated dashboard
Reads every reconcilable repo's worksheet (over local clones), emits
`PlatformManifest/docs/architecture/console-reconciliation-status.md`: public repos
itemized (counts done/partial/incomplete, doc-gaps, prune-ready bool); private repos
as a single opaque aggregate count (never itemized). Owner fields genericized.

**AC11:** the generated status names only public repos; private repos contribute a
count with no identifying detail.

## §4 Layer C — Archive (private-manifest repo)
Layout `<private-manifest-repo>/archive/console/<repo>/{log,backlog}-<cutoff>.md`. Append-only.
The private side may freely contain scrub-target names (they're allowed there).
Public repo retains only the pointer + CHANGELOG summary.

**AC12:** archived files exist on the private side after pilot prune; the public
Custodian repo retains a pointer line referencing the archive without leaking names.

## §5 Pilot — Custodian (proves the whole chain)
1. Author `Custodian/.console/reconcile.yaml` classifying its items (use the
   first-draft table as input; `done`/`partial`/`incomplete` + owner).
2. Fill the 7 DOC GAPs — **catalog entry in the matrix AND full usage docs w/ examples**:
   T6, T7, T8 (test-presence trio), X3 (stale GitHub URL), CV1/CV2/CV3 (coverage adapter).
3. Scrub the scrub-target identifiers from tracked `docs/` (genericize prose
   private-name refs; detector-ID forms are exempt by word-boundary matching)
   and any tracked `.console/` content that will *remain* (active sections).
4. Route the 3 cross-repo "open" rows (owner = a private downstream repo /
   OperationsCenter / SwitchBoard) out of Custodian's backlog.
5. `cl reconcile check` green → `cl reconcile prune --apply` → recompile
   `.console/.context` → verify size drop + R2 clean.

**AC13 (pilot done):** Custodian `check` green, R1/R2 clean, completed history in
the private archive, tracked `.console/` slim + scrubbed, 7 detectors documented
(catalog + usage), CHANGELOG updated, all Custodian tests + audit green.

## §6 Verification (every phase)
- New code has tests; existing suites stay green.
- I2 spot-check: `git grep` for the scrub-target identifiers (the boundary-artifact
  pattern) on tracked files of each touched public repo returns nothing (detector
  IDs like the `<XX>2` family excluded by word-boundary matching).
- No `PrivateManifest` literal added to CL source (discovery/env only).

## §7 Out of scope (tracked separately)
- ~~Fleet-wide prune beyond the Custodian pilot (run after pilot sign-off).~~
  **Shipped 2026-06-04/05** — pilot signed off and the prune ran fleet-wide
  (archives under the private manifest's `archive/console/<repo>/`); see
  [console-reconciliation-status.md](console-reconciliation-status.md).
- The PrivateManifest → role-discovery generalization ([[private-manifest-generalization]]).
- ~~OperationsCenter prune (needs a paused-loop window).~~ **Shipped
  2026-06-04** — run during a paused-loop window per the documented procedure.
