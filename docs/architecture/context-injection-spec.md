# Tiered Memory & Context Injection — Draft Spec

> **Status:** DRAFT / discussion checkpoint — not yet approved for build.
> **Date:** 2026-06-02
> **Extends:** ContextGuard, ContextLifecycle anchoring, OperatorConsole.
> **Primary concern:** the *memory structure* — what is stored, how it is
> tiered, captured, consolidated, and retrieved. Hook/CLI plumbing is secondary
> (§6).
>
> **Reading order matters:** §2 defines the model *within a single repo*
> (project scope — what v1 builds). The cross-repo scope axis (§2.5) is
> design-locked but build-deferred. Earlier drafts described an upward
> "promote-to-global" flow; that was **retired** — see §2.5 for why.

---

## 0. Problem statement

We have enforcement (ContextGuard blocks bad tool calls) and a bloated
always-loaded blob (`.console/.context`, ~1800 lines). What we lack is a
**durable, tiered, retrievable knowledge store with injection timed to the
edit**. Knowledge an agent discovers dies at session end inside
`.context/sessions/` capsules; nothing distills it or puts it back in front of
the next agent at the moment it edits the relevant code.

The article that inspired this (Patterson, hook-based context injection) is
treated as **intent only**: we adopt the idea (inject the right doc right before
the edit), not the implementation (Node, co-located docs). Constraints: bash +
python3, no Node runtime, one engine serving multiple CLIs.

### 0.2 Key terminology

- **Anchor** — always-loaded repository truths.
- **Router** — glob matcher triggering injection.
- **Consolidation** — campaign-scoped distillation of findings.
- **Injection** — passing docs to agent pre-edit based on file path.

### 0.1 Relationship to the memory stores that already exist

This spec must **not** create a fourth parallel memory store. The boundary:

| Store | Scope | Curated by | Role here |
|-------|-------|-----------|-----------|
| `.console/` (task/backlog/log) | this repo | human | **unchanged** — high-level work tracking, the campaign boundary signal |
| `~/.claude/projects/.../memory/` | operator-global, cross-repo | agent | **out of scope** — operator's own memory; a *future* sync target, not touched here |
| `.context/knowledge/` (**new**) | this repo, committed | agent + consolidation | the project-tier **cold store** this spec defines |

Decision: the cold store is **repo-committed project knowledge** (`.context/
knowledge/`), deliberately distinct from `~/.claude` operator memory. Project
knowledge travels with the repo and is shared across operators/CLIs; `~/.claude`
memory is per-operator and machine-local. Merging them is the *separate*
consolidation/sync task the operator already deferred — this spec does not
depend on it and does not pre-empt it.

---

## 1. Where logic vs state lives

The engine is **ContextLifecycle tooling**, not repo content — authored in the
CL repo, *installed* into consumer repos by `provision.sh` / shim installers,
like git ships `.git/hooks` runners without living in your tree.

| Thing | Authored in | Lands in | Committed? |
|-------|-------------|----------|------------|
| Engine code (route/inject/enforce/consolidate) | **CL repo** | `.context/.engine/` (vendored) or `cl` on `$PATH` | no — provisioned |
| `routes.yaml` (repo-specific routing) | this repo | `.context/routes.yaml` | yes |
| Leaf docs (warm memory) | this repo | `docs/inject/*.md` | yes |
| Cold knowledge store | this repo | `.context/knowledge/` | yes |
| Session capsules (ephemeral) | runtime | `.context/sessions/` | no (gitignored, pruned) |

`.context/` is a **mount point** where CL operates, not the home of CL's logic.

**Version compatibility:** the engine floats (provisioned) while `routes.yaml`
and cold front-matter are committed (pinned to the repo). To avoid skew, the
engine declares a `schema_version`, `routes.yaml` carries a matching
`engine_compat:` field, and the engine **warns and degrades gracefully** (skips
injection, never blocks) on mismatch rather than misparsing. `cl context init`
(see §6) writes a `routes.yaml` stamped for the installed engine.

---

## 2. The memory model (project scope)

Four tiers, distinguished by **lifespan and always-on token cost**. Higher tier
= more expensive to keep loaded = stricter eviction. Most knowledge should rest
in cold and surface only when relevant.

```
  cost to keep ▲
  HOT  / anchor     │  always loaded      universal repo-wide truths    ~tens of lines, kept tiny
  WARM / injected   │  pushed on edit     per-domain conventions        20-40 lines each
  COLD / knowledge  │  surfaced on match  full findings + detail        unbounded, indexed
  EPHEMERAL/capsule │  this session only  in-flight investigation       discarded or sealed to cold
```

### 2.1 The four tiers concretely

| Tier | Lives in | Loaded when | Format | Written by |
|------|----------|-------------|--------|------------|
| **Hot** | trimmed `.console/.context` + repo anchor | every session start | terse facts, layer map, routing pointer | human + consolidation |
| **Warm** | `docs/inject/*.md` (`## Inject` block) | router pushes on matching edit | 20-40 line convention list | distilled from cold |
| **Cold** | `.context/knowledge/*.md` | router surfaces matching topics; explicit query | full doc, front-matter indexed | sealed from capsules |
| **Ephemeral** | `.context/sessions/<sid>/` | active session | capsule YAML | the running agent |

The tier promotions that happen **within a repo** (the v1 scope) are
cold→warm (distill a recurring finding into an injected leaf doc) and warm→hot
(a fact so universal it belongs in always-on anchor context). Both are
*automatic but strict*, gated by §2.4. Neither crosses repos — cross-repo flow
is §2.5 and is deferred.

### 2.2 The lifecycle — capture continuous, consolidate per-campaign

```
 EPHEMERAL ──seal──► COLD ──distill──► WARM ──(rare)──► HOT
 (capsule)   (Stop)  (knowledge/)     (docs/inject)    (anchor)
                        ▲                   │
                        └── prune / merge / demote-if-stale ──┘
```

Consolidation's **unit is the campaign, not the session.** A campaign is a
bounded set of runs toward one objective; per-session consolidation is rejected
as wasteful (most sessions produce nothing durable). Cost scales with campaigns,
not sessions.

1. **Capture (continuous, cheap).** The agent appends findings to its capsule as
   it works. This is the pipeline's intake and must not depend on goodwill alone
   (see §2.3 for the forcing function) — an empty capsule starves everything
   downstream.
2. **Seal (Stop hook).** The Stop hook flushes the capsule's findings into the
   cold store with front-matter (§2.4). It does no distillation — just persists
   what was captured so a closed session isn't lost.
3. **Consolidate (per-campaign, rare, thorough).** On campaign close, one
   `cl consolidate` pass over the campaign's cold accumulation does the
   expensive thinking: **distill** recurring findings cold→warm, **prune/merge**
   duplicates, **demote** stale warm/hot, and **prune session dirs**. Because it
   runs rarely it can afford to be thorough.

Discipline: **capture is cheap and ungated** (lose nothing); **promotion is rare
and strict** (§2.4). The expensive work happens once per campaign.

### 2.2b Campaign formalization (the consolidation boundary)

The campaign is the consolidation unit, but `.console/` doesn't express a
campaign boundary today. `task.md`'s own instructions say *"replace contents when
the objective changes; do not accumulate history"* — overwrite-in-place with
**no close event**, so the boundary is lossy (old objective clobbered) and
implicit. It must be formalized — and this front-matter is the **prerequisite**
for §2.3's automatic trigger and §2.6's `campaign_id` tagging:

```markdown
# Task
---
campaign_id: c-2026-06-02-9f3a   # minted at campaign start, inherited by every session
status: active                   # active | done
started: 2026-06-02
---
## Objective
...
## Definition of Done
...
```

- **`campaign_id`** is minted when a campaign starts, stored here, and inherited
  by every session during it — so every sealed cold item (§2.6) is tagged with
  it and consolidation can select exactly the campaign's accumulation. (Sessions
  are tagged by session id today, too fine-grained to bound a campaign.)
- **Close** has two paths: the explicit `cl campaign close` transaction (read
  closing task → `cl consolidate` over items with that `campaign_id` → append a
  record to `log.md` → reset `task.md`), **and** the automatic fallback in §2.3
  for when nobody runs the command. `status: done` is the declarative signal a
  human/agent flips; the command/fallback is the machinery that acts on it.

Division of labor unchanged: OperatorConsole is the human surface,
ContextLifecycle is the machinery that reads/writes it.

### 2.3 Intake reliability — capture and trigger forcing functions

The intake is the weakest link (an agent that never journals → empty cold →
dead pipeline), and the repo proves manual lifecycle commands don't get run
(54 orphaned session dirs because `cl session end` is never called). So neither
capture nor consolidation may rely on discipline alone:

- **Capture forcing function.** ContextGuard's Stop hook *already* warns when no
  checkpoint was written. Extend that: on Stop, if the capsule has no findings
  for a session that made edits, the hook prompts for a one-line capture (or
  records "no durable findings" explicitly). Capture becomes the path of least
  resistance, not an optional chore.
- **Automatic consolidation trigger.** `cl campaign close` stays as the explicit
  path, but consolidation **also fires automatically** when the campaign
  boundary changes without an explicit close — i.e. when `.console/task.md`'s
  `campaign_id` changes or its `Objective` is overwritten (the detectable
  successor to today's overwrite-in-place). A periodic fallback
  (e.g. on session start, if the prior campaign never consolidated) catches the
  rest. The boundary is detected, never solely declared.
- **Cold read trigger (cold must not be write-only).** Warm is pushed by the
  router; cold would otherwise be queried by nobody and become a write-only log.
  Fix: the **same router pass that injects warm leaf docs also surfaces matching
  cold topics** — not the full docs, just a one-line index (`topic — path —
  one-line finding`) so the agent knows relevant detail exists and can pull it.
  Cold is thereby *surfaced* automatically and *expanded* on demand.

### 2.4 Promotion gate — consequence + usage, not vote-counting

Promotion (cold→warm, warm→hot) is automatic, so the gate is the only guardrail.
There is **no ground-truth oracle** for "is this architectural fact true," so
the gate does not try to certify truth — it gates on signals the agent **cannot
fake**:

1. **Consequence as a veto.** A finding is ineligible to promote unless it was
   *acted on and survived*: the change relying on it **landed in a commit and
   tests stayed green**, or the convention **stopped a logged violation from
   recurring**. This rejects un-acted-on assertions. It does **not** certify
   truth (tests only cover what they cover) — necessary, not sufficient.
2. **Usage-based staleness.** A warm fact still injected on matching edits is
   implicitly re-exercised and stays; one nothing matches anymore **decays**.
   **Exception — pinned files:** facts about flagged critical/rare-edit paths
   (e.g. visibility boundaries) are **pinned and exempt from decay**, so
   high-stakes low-frequency knowledge is not evicted (the failure mode of naive
   usage-decay).

**Retired and why:** self-reported confidence (agent-controlled, theatre);
`cited_sessions` vote-counting (certifies repetition, not truth;
injection-contaminated — a later session "cites" what we injected;
anti-correlated — rarely-touched code is "never contradicted" only because
nothing exercises it); change-based TTL on referenced paths (churns the hottest,
most-needed files to stale on every unrelated edit). Content-hash drift is kept
only as a **flag-for-review** signal, never an auto-demote.

**Warm is not "cheap to be wrong."** A wrong warm doc is injected on *every*
matching edit at the highest-attention position, actively steering the agent —
so the consequence-veto + decay apply to cold→warm, not only to scope.

### 2.5 Cross-repo scope — publish-down, design-locked, build-deferred

Memory also has a **scope axis**: the manifest anchor chain
(`local → work_scope → project → platform`). "Cross-repo memory" = memory
anchored at a higher manifest, inherited by resolving the chain upward. The
design is settled; the **build is deferred** (§7b). The settled rules:

- **Publish-down (authoritative).** The manifest that *owns* a shared contract
  (manifest schemas, projection/visibility rules, the anchor protocol) authors
  and validates facts about it where the contract lives; consumers inherit by
  anchoring up. Safe because the **owner's own schema/tests are the oracle**, and
  staleness is well-defined (the owner's contract files change in one known
  place, one commit).
- **Bubble-up is a report, never a promotion.** A consumer that notices
  something about a shared contract files a **candidate note into the owner's
  cold store** — a queued suggestion the owner triages, never an unsupervised
  global write.

**Retired:** upward auto-promotion of a consumer's generalization to global
authority (no oracle; "re-derivation elsewhere" is echo-contaminated once the
fact is injected there), and the advisory-label dodge (self-contradictory — the
spec exists because injection *steers*; a label that reliably stopped the model
heeding the injection would also defeat the warm tier). Direction, not hedging,
is the fix.

### 2.6 Cold store item format

```markdown
<!-- .context/knowledge/projection-redaction-ordering.md -->
---
topic: projection
paths: ["src/platform_manifest/projection/**"]
created: 2026-06-02
campaign_id: c-2026-06-02-9f3a        # which campaign sealed it
consequence:                          # the unfakeable promotion signal
  acted_on_commit: <sha|null>         # change relying on it that landed
  tests_green: true|false|unknown
tier: cold                            # cold | warm | hot
pinned: false                         # exempt from usage-decay if true
last_injected: <date|null>            # usage-decay reads this
---
## Finding
Redaction must run before validation, or private fields leak into the
projected schema.
## Detail
<full reasoning, repro, links>
```

The distill/prune pass reads `consequence`, `last_injected`, and `pinned` — not
self-reported confidence or citation counts.

---

## 3. Warm tier: routing table + leaf docs

`routes.yaml` is glob → doc-list, **all-matches** (every matching rule fires):

```yaml
# .context/routes.yaml
engine_compat: ">=0.2 <0.3"     # guards against engine/routes skew (§1); matches clp_version 0.2
budget:
  max_docs_per_edit: 3          # cap injected breadth (see below)
routes:
  - match: "src/platform_manifest/loader.py"
    inject: ["docs/inject/loader.md"]
    priority: 10
  - match: "src/platform_manifest/projection/**"
    inject: ["docs/inject/projection.md", "docs/inject/visibility.md"]
    priority: 20
  - match: "src/platform_manifest/schemas/*.json"
    inject: ["docs/inject/schemas.md"]
  - match: "scripts/provision*.sh"
    inject: ["docs/inject/provisioning.md"]
```

Leaf doc = `## Inject` (emitted, 20-40 lines, non-obvious conventions only) +
`## Reference` (not emitted; read on request — a pointer into cold).

**Injection budget (was unbounded).** All-matches can flood context (3 routes ×
40 lines, every edit, at the highest-attention position). So routing is capped:
`max_docs_per_edit` bounds breadth, `priority` orders which docs win when more
match than the cap allows, and per-session recency dedup (§6) suppresses
repeats. When the cap truncates, the engine logs what it dropped (no silent
truncation).

**Decision B (leaf doc location):** central `docs/inject/`, not co-located.

---

## 4. Enforcement tier

- Existing ContextGuard scope/lease/budget checks: unchanged.
- **A passive warn-only violation logger ships in v1** (not zero
  instrumentation). It records would-be violations without blocking; blocking
  rules are seeded *from that log* once real patterns emerge. The logger is what
  makes "grow rules from data" possible *and* feeds the consequence-veto's
  "stopped a logged violation from recurring" signal (§2.4).
- claude post-tool can only block via exit 2 + stderr (`additionalContext` JSON
  unsupported) — logger and future rules use that path.

---

## 5. Hot tier: trim `.console/.context`

Target: a **small** anchor (layer map, dependency direction, pointer to where
routing/cold live, hard rules) — order ~150 lines, but the real target is "only
what is universally true and must be present every session"; tune to that, not
a line count. Backlog/log/task stay as `.console/` source, no longer all
compiled into the always-loaded blob.

**The doc-reconciliation pass is decoupled** (it is a documentation project, not
part of the engine build): walk `.console/backlog.md`, mark items
done/partial/not-started, verify "done" against repo reality, migrate durable
knowledge into the cold store, group/archive stale entries, and refresh the
external doc surface — the **`ProtocolWarden`** repo and **`protocolwarden.github.io`**
(Decision C). Tracked as its own track (§7c), runnable independently of phases
1–5.

---

## 6. Hook plumbing (secondary)

One CLI-agnostic core (in CL repo, installed here), thin per-CLI shims.

**Decision A (multi-CLI scope):** **claude is the reference model** — the only
CLI with a pre-tool hook that can both inject and block. Build the full pipeline
for claude.
- **codex**: post-tool hooks only → enforcement/logging only, no pre-edit
  injection. Wire when it ships pre-tool support.
- **aider**: no hook support → hot tier only. Revisit if it adds hooks.

Normalized contract every shim emits to the core:
`{ event, tool, path (repo-relative, $PROJECT_DIR stripped), cli }`.

**Init/setup (needed, not yet written):** `cl context init` scaffolds
`routes.yaml` (stamped `engine_compat:`), `docs/inject/`, `.context/knowledge/`,
and installs the claude shim; idempotent for re-run during provisioning.

**Dedup:** no *global* cross-agent cache (broke parallel subagents), but a
**per-session recency guard** keyed on (path + doc hash) so the same block isn't
re-injected on repeat edits.

**Config flag (Decision D):** `injection.enabled` in `config.yaml` ships
injection dark for one validation window, **with a committed date to default-on
after phase 2** — not indefinite dark.

---

## 7. Build phases

**v1 scope: project tier only**, single-repo. The cross-repo axis (§2.5) is
design-locked, build-deferred (§7b). **Phases 3–5 are gated** (§7a) — build the
cheap high-value half first, then decide whether the rest pays off.

1. **Engine home + extract.** Author the core in the CL repo; install to
   `.context/.engine/`. Move `pre_tool_use.sh` logic into it; shrink the claude
   shim. Prove parity (no behavior change).
2. **Warm injection (claude).** `routes.yaml` (with budget + `engine_compat:`),
   router, 3–4 leaf docs, per-session dedup. Flip `injection.enabled` on.
   Validate: does the right doc appear right before the edit, within budget?

### 7a. Gate — evaluate before building the pipeline

After phase 2 runs in the wild for a real validation window, answer: **did warm
injection demonstrably reduce convention violations / rework?** If no, stop here
— hot-trim + warm-injection may be the whole win at this scale, and the cold/
consolidation pipeline is speculative weight. If yes, proceed:

3. **Cold store + capture/seal/surface (project scope).** `.context/knowledge/`
   format (§2.6), continuous capture + the Stop-hook forcing function (§2.3),
   grep index, **cold-topic surfacing in the router**, warn-only logger.
4. **Hot trim.** Shrink `.console/.context` to the anchor (§5). (Doc
   reconciliation runs separately — §7c.)
5. **Campaign consolidation (`cl consolidate`, project scope).** First land the
   `task.md` front-matter (§2.2b) — prerequisite for the trigger. Then:
   campaign-close trigger *with automatic fallback* (§2.3), distill cold→warm
   under the consequence-veto + usage-decay-with-pinning (§2.4), session-dir
   pruning.

### 7b. Platform tier — design locked, build deferred

Cross-scope design is settled (§2.5). Not built in v1 because (a) publish-down's
safely-validatable subset largely overlaps the schema validation the loader
*already* enforces — the high-value cross-repo knowledge is the un-validatable
kind that stays project-local; and (b) owner-keyed downward invalidation needs a
cross-repo sync channel that doesn't exist yet. **Unlock when:** that sync
channel exists, repo count makes manual cross-pollination painful, and the
project tier has shown what cross-repo knowledge concretely looks like. Until
then, move cross-repo facts **manually**.

### 7c. Doc-reconciliation track (independent)

Decoupled from the engine build (§5). Runnable any time; touches `.console/`,
the cold store, and the external doc surface (ProtocolWarden +
protocolwarden.github.io).

---

## 8. Resolved decisions

- **A** — claude-only injection; codex = post-tool enforcement later; aider =
  hot tier only.
- **B** — leaf docs central in `docs/inject/`.
- **C** — external doc surface = `ProtocolWarden` + `protocolwarden.github.io`;
  reconciliation is its own track (§7c), not coupled to the build.
- **D** — `injection.enabled` flag, dark one window then default-on.
- **Memory model:** four tiers by lifespan/cost; promotions cold→warm→hot are
  in-repo only and gated by consequence-veto + usage-decay-with-pinning;
  vote-counting and self-confidence retired.
- **Intake:** capture continuous with a Stop-hook forcing function; consolidation
  campaign-scoped with an *automatic* trigger (not a manual command alone);
  cold surfaced by the router so it isn't write-only.
- **Cross-repo (§2.5):** publish-down from the owning manifest, bubble-up only as
  a candidate note to the owner; design-locked, build-deferred.
- **Store boundary (§0.1):** cold = repo-committed `.context/knowledge/`;
  `~/.claude` operator memory is untouched, a separate future sync task.
- **Caps & compat:** injection budget (`max_docs_per_edit` + priority);
  `engine_compat:` guards engine/routes skew, degrading to no-injection on
  mismatch.

## 9. Still open

- **Capture forcing function — how hard?** Prompt-on-Stop (soft) vs block-stop-
  until-captured (hard, risks the "parole officer" pain). Leaning soft, with the
  warn already in `stop.sh`.
- **Automatic consolidation trigger reliability.** Is "objective overwritten /
  `campaign_id` changed" detectable cleanly given task.md is freeform today, or
  does it need the §2.2b front-matter to land first? (Likely: front-matter is a
  prerequisite — it is listed as such in §2.2b.)
- **Consequence-veto wiring & attribution.** How does the engine observe "landed
  + tests green" and attribute it to a finding beyond fuzzy path-proximity?
- **Cold-surfacing noise.** One-line cold topics injected alongside warm — does
  this re-bloat the high-attention position the budget just protected? Needs a
  separate (smaller) cap.
- **Usage-decay threshold & pin authority.** How many no-injection campaigns
  before decay; who marks a file pinned (manual list vs derived from
  visibility-boundary metadata already in the manifest)?
- **"Owned contract" definition (for §2.5 when unlocked).** The line between an
  ownable, schema-validatable contract fact and a general convention that must
  stay project-local.
