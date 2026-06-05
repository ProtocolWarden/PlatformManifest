# Cognition & Memory Architecture — Overview

_The connecting document. Each subsystem below has its own deep spec (linked);
this page exists so an operator can re-orient on how they fit together without
re-deriving it. Written 2026-06-05, after the fleet reconciliation and
context-injection arcs closed._

## The one-paragraph version

Agent sessions anchor to a **cognition host** (a manifest repo) rather than the
repo they're editing. Everything a session learns flows through a **tier
model**: in-flight scratch state stays machine-local and disposable; durable
insight is captured in `.console/log.md`, periodically **reconciled** (distilled
into real docs, history archived, size enforced), and the highest-value
conventions are promoted into **warm leaf docs** that get **injected** back
into future sessions automatically at edit time. Git is the only cross-machine
transport for all of it — continuity is carried by commits, never by session
files.

## 1. Cognition hosts and anchoring

Cognition state lives in a `.context/` directory — but only in **two repos**,
the manifest repos. Working repos do not host their own cognition; their
sessions *anchor* to the owning manifest via ContextLifecycle
(`cl session start` → `CL_ANCHOR` env var).

| Cognition host | Who anchors there |
|---|---|
| **PlatformManifest** | its own operator sessions; OperationsCenter pipeline lanes + loop controller; OperatorConsole panes for public repos |
| **PrivateManifest** | the private downstream repos' hooks and loop controllers; OperatorConsole panes for private repos |

Key consequences:

- **OperationsCenter has no `.context/` by design** (its `.gitignore` records
  the removal decision). Its hooks *block* every tool call unless `CL_ANCHOR`
  is set, and resolve all state from the anchor. Its executor backends are
  instrumented one level deeper: every dispatch is wrapped in a lineage-scoped
  hydrate/capture (`cl_wrap.py`) that inherits the anchor from the launching
  process and no-ops when unanchored — the source of the `l-*.yaml` lease
  records under the anchor's sessions. The same pattern applies on
  the private side.
- OperatorConsole resolves each pane's owning manifest dynamically
  (test-enforced — no hardcoded anchor), and its post-session shell shims
  `claude` so a bare re-launch re-anchors.
- Most public repos (~17) have no hooks and no anchoring at all. Custodian is
  the exception: it carries a stateless `.context/` (routing config only, no
  sessions) for warm injection — config, not cognition.

Deep docs: [contextlifecycle-anchoring.md](contextlifecycle-anchoring.md).

## 2. The tier model and what each tier is for

| Tier | Contents | Lives in | Purpose |
|---|---|---|---|
| **Hot** | compiled `.console/.context` startup blob | generated at launch, gitignored | what a session reads first; trimmed to the anchor (active task, guidelines, recent log) |
| **`.console/` truth** | `task.md`, `guidelines.md`, `backlog.md`, `log.md` | tracked in git | the editable source of the hot tier; `log.md` is the **capture surface** for session insights |
| **Warm** | `docs/inject/*.md` leaf docs + `.context/routes.yaml` | tracked in git | conventions injected into sessions automatically when they edit matching paths |
| **Cold** | `.context/knowledge/` entries | tracked in git | manual-only micro-insight store; surfaced by the router as "related cold topics" |
| **Session** | `.context/sessions/`, `archived/` (capsules, leases, checkpoints) | machine-local, gitignored | in-flight scratch for one session on one machine; disposable once work is committed |

The invariant that makes the whole design safe: **a session file must never
hold the only copy of anything worth keeping.** If it does, the workflow bug is
"work wasn't committed/captured," not "sessions should sync."

Deep docs: [context-injection-spec.md](context-injection-spec.md) (tiers,
router, engine), [context-injection-work-order.md](context-injection-work-order.md)
(what was built, gate decisions, closures).

## 3. Cross-machine sync — what travels and how

Two transports exist; nothing else moves between machines.

1. **Git** carries every durable tier: `.console/` truth, warm leaf docs +
   routes, cold knowledge, the engine itself. A fresh clone gets working
   injection with zero setup.
2. **The fleet sync layer** (a private repo's Syncthing topology) carries only
   its explicitly declared data folders (config/asset/backup buckets). No repo
   trees, no `.context/`.

Everything else is **machine-local by design**:

- The hot tier is *regenerated* on each machine from tracked sources — both
  machines end up with equivalent compiled context without ever syncing a file.
- Session state syncs via nothing. Each host's sessions reconstruct from its
  own local cognition host. Multiple machines run sessions against the same
  remotes concurrently — git is the merge point, and races are resolved with
  ordinary rebase (this happened mid-reconciliation and was recoverable
  precisely because prune is idempotent and the archive is append-only).

## 4. The knowledge lifecycle (capture → consolidate → inject)

The pipeline that actually carries insight from a session back into future
sessions:

```
session does work
  → durable narrative lands in .console/log.md        (capture; R1 caps size)
  → cl reconcile: worksheet classifies done threads,
    doc-gap gate blocks pruning anything undocumented,
    prune archives history to the private side          (consolidate)
  → distilled conventions become docs/inject/ leaf docs (promote)
  → the router injects them into future sessions
    editing matching paths                              (inject)
```

Notes on this pipeline:

- It is **enforced, not aspirational**: Custodian's R1 detector fails the audit
  when a `.console` log exceeds its line budget, forcing the
  capture→consolidate cycle; the reconcile doc-gap gate refuses to prune
  history whose value isn't in real docs; R2 keeps private names off public
  `.console` surfaces.
- The original spec designed a separate automated capture path into the cold
  store (phase 3). It was **closed as superseded** (2026-06-05): `.console/log.md`
  won as the capture surface — tracked, synced, human-readable, and gated.
  The cold store remains live as a manual-only surface.
- All 22 fleet repos (19 public + 3 private) are reconciled and enforcing as
  of 2026-06-04; the status dashboard is generated, not hand-edited.

Deep docs: [console-reconciliation-spec.md](console-reconciliation-spec.md)
(R1/R2, worksheet, gate), [console-reconciliation.md](console-reconciliation.md)
(design), [console-reconciliation-status.md](console-reconciliation-status.md)
(dashboard).

## 5. Injection consumers (warm tier in practice)

| Repo | Hook | Behaviour |
|---|---|---|
| PlatformManifest | full ContextGuard PreToolUse hook | guard checks + injection |
| Custodian | slim injection-only hook | never blocks, always exit 0; the template for future consumers |

When a session edits a path matching `.context/routes.yaml` (e.g. CI workflow
files route to the ci-conventions leaf doc), the engine injects the leaf doc as
additional context *before* the edit — conventions get followed instead of
re-derived. OperationsCenter and the private downstream repos are deliberately
**not** consumers: anchor-hosted cognition means repo-local routing can't match
their checkout paths — that's the deferred cross-repo tier (spec §2.5/§7b).

## 6. The privacy boundary, in one place

- The **public/private boundary** is enforced by a generated boundary artifact
  (`forbidden_names`), consumed by Custodian's B-class/R2 detectors and the
  reconcile gate. Private repo names must never appear in public repos' tracked
  files.
- Private repos are exempt from scrub semantics *on their own surfaces* —
  detected by self-name match or by being the private-manifest root itself.
- Pruned `.console` history archives to the **private side**
  (`<private-manifest>/archive/console/<repo>/`) regardless of source repo —
  history keeps its real names there.
- Private-side cognition (PrivateManifest's `.context/`) must never leak into
  public trees.

Deep docs: [visibility_boundary.md](visibility_boundary.md),
[public_private_projection.md](public_private_projection.md),
[private-manifest-role-generalization.md](private-manifest-role-generalization.md).

## 7. What is deliberately NOT built

| Deferred item | Why |
|---|---|
| Cross-repo/platform injection tier | OperationsCenter + private downstream repos are the motivating case; revisit only if their sessions demonstrably re-derive conventions (spec §7b) |
| Cross-machine session continuity | continuity is carried by commits; syncing sessions would be a deliberate design choice, not a fix |
| Automated cold-store capture (phase 3) | closed as superseded by the `.console` pipeline (2026-06-05); cold store is manual-only |
| Operator-memory ↔ cold-store merge | `~/.claude` memory and repo cold stores serve different scopes; merge deferred |
