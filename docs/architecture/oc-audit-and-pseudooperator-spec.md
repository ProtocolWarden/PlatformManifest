# OC Audit Findings + PseudoOperator Spec

**Status:** design checkpoint — grounded audit with file:line receipts; not yet approved for build  
**Date:** 2026-06-26  
**Scope:** OperationsCenter + VF controllers; precondition for PseudoOperator formalization and restorer/anchor work

---

## What the audit overturned

Two doc claims were wrong and are corrected here before any build work starts.

**"VF is an OC component / two controllers in OC" — WRONG.**  
VF has its own loop (`VF/tools/loop/controller.py`) and OC has its own (`OperationsCenter/tools/loop/controller.py`). They are near-identical copy-paste files differing only in `REPO_ROOT`, model, prompt text, and delay constants. OC's audit dispatch fires a VF audit as a one-shot subprocess and reports status — it never investigates or fixes. The real VF audit→investigate→fix→relaunch loop lives in VF, not OC.

**"The anchor doesn't exist yet" — PARTIALLY WRONG.**  
The EVAL corpus is already ed25519-signed, hash-chained, and CODEOWNERS-pinned to `@ProtocolWarden` (`eval/verify.py`, `eval/constitution/operator_pubkey.ed25519`). Monotonicity is real: "BASELINE LOWERED" fails the build. But all of it governs only the eval exam floor — none governs the live policy/autonomy plane. The anchor exists in one plane and is absent in the other.

---

## 1. Verified role mapping

| Doc role | Real code | Verdict |
|---|---|---|
| **Data plane** | `board_worker` fleet + `execute` + Team/DAG executors | exists 1:1 |
| **Control plane** | pr_review_watcher (9 task types) + two `tools/loop/controller.py` copies | exists, but copy-paste not one component |
| **Verifier** | `drift/engine.py` (checks drift, not against a signed ref) + EVAL gate (vs signed answer key) | partial — nothing checks live config against a signed reference |
| **Restorer** | only controller_liveness (process-level, not config-level) | genuinely absent |
| **Trust anchor** | EVAL ed25519 corpus + `[check: ref]` ledger | exists 1:1 — but eval plane only |

**Verdict: ~60% relabel, ~40% genuinely new.** The new 40% is: a signed-config restorer in the live plane, and a no-self-rewrite invariant there. Both exist in the eval plane today; neither exists in the live policy/autonomy plane.

---

## 2. Defects — grounded with file:line

### Policy and gates

**🔴 Forgeable trusted-source bypass**  
`source: autonomy`, `source: board_worker`, `source: spec-campaign` labels set `trusted=True` and skip the risk + task-type review gates (`policy/engine.py:521-568`). These are plain GitHub issue labels — any author can add them. Labels propagate to re-queued children. A feature task labeled `source: autonomy` skips the review it would otherwise require.  
*Fix: author allowlist gates the trusted-source labels; labels must be set only by the controller's service account, not by the task author.*

**🔴 Policy inspects declared scope, not the agent's diff**  
`engine.py:270` runs the scope check against the PR's stated scope claim, not the actual diff content. The post-write gate runs in the same process — bypassable.  
*Fix: scope-check must run against the committed diff, not the task's self-declared scope.*

**🔴 Self-merge to main by default**  
The require_branch_protection setting defaults False (`config/settings.py:313`). The reviewer issues `reviewer-verdict=success` and merges its own CI-green, self-LGTM'd PR via plain REST PUT (`pr_review_watcher/main.py:1265-1274`). Branch protection on these repos is out-of-band (GitHub org settings) — this works only because the operator configured it externally. The code itself does not enforce it.  
*Fix: default `True`; fail closed if the protection check call returns an error.*

### Containment and liveness

**🔴 Write-capable git token in the least-trusted agent's env**  
`board_worker/_subprocess.py:172` forwards the full `GITHUB_TOKEN` (long-lived `gho_` OAuth token, write-capable across all owned repos) into the bwrap sandbox `--setenv`. The sandbox runs arbitrary LLM-generated code.  
*Fix: per-task GitHub App installation token (1h TTL, one-repo scope). Raw credential never in sandbox env — inject only the derived `GIT_CONFIG` header. Spec: `docs/architecture/sandbox-token-hardening-spec.md`.*

**🔴 Triple fail-open containment**  
`bwrap`, `netns`, and egress are all off-by-default and fail-open. `OC_BWRAP_SANDBOX`, `OC_NETNS_REQUIRED`, `OC_EGRESS_REQUIRED` flags are absent from the shipped env. A missing binary or an argv throw silently degrades to an unsandboxed, host-FS, open-network run (`board_worker/sandbox.py`, `netns.py`).  
*Fix: default all three to required; on missing binary, fail the task (not the fleet); add a startup self-check that verifies containment before accepting work.*

**🔴 No executor timeout on the board path**  
`board_worker/_subprocess.py:337` has no timeout. A hung agent pins a worker slot forever. The reviewer path caps at 1800s; the board path does not.  
*Fix: add `timeout=` param; make it configurable; default to something sensible (e.g. 3600s matching the sandbox TTL).*

### VF loop specifically

**🔴 Guardrails are 100% prompt-side**  
The VF controller (`VF/tools/loop/controller.py`) runs the agent with `--dangerously-skip-permissions`, no conversation history, and re-spawns unconditionally. The confidence floor, max-cycle cap, and failure caps all live only as prose in `vf_session_prompt.txt`. If the prompt is ignored or the agent diverges, nothing enforces the limits.  
*Fix: move caps into controller code (cycle counter, failure counter, hard stop). Prompt-prose is advisory, not enforcement.*

**🔴 VF controller: broken locking + no timeout**  
Non-atomic TOCTOU lock (`os.path.exists` + `open`), broken stale-lock reclaim (ignores hostname in lock file), cooldown can busy-spin, `subprocess.run` at `controller.py:635` has no timeout — a hung VF session blocks the controller loop forever.  
*Fix: atomic lock (`O_CREAT|O_EXCL`), hostname-aware stale check, hard subprocess timeout.*

**🔴 OC audit dispatch: timeout=None + premature lock release**  
The audit dispatch module uses `timeout=None` by default — a wedged VF audit hangs OC's audit dispatch loop forever. Lock is released while child is still running; status is reported as `COMPLETED` despite `status: in_progress`.  
*Fix: explicit timeout (e.g. 30min); hold lock until child exits.*

---

## 3. Is the restorer the anchor? No — three distinct roles

| Role | Acts? | In/out of bounds | Exists today? |
|---|---|---|---|
| **PseudoOperator** (formalized VF/OC controller) | yes — runs tasks, drives convergence | in-bounds | yes, as two copy-paste loops |
| **Restorer** | yes — deploys signed config to PseudoOperator | in-bounds (the only writer) | no — genuinely new |
| **Anchor** (out-of-bounds supervisor) | no — inert signed reference only | out-of-bounds (fleet cannot reach) | partially — EVAL ed25519 corpus is the template; live-plane anchor absent |

The restorer is the in-bounds hand that applies; the anchor is the out-of-bounds root that authorizes. The reason "out-of-bounds" is the right word: the only gates that actually hold today are out-of-bounds — the ed25519 corpus, CODEOWNERS, and GitHub branch protection that the fleet doesn't control. Every in-bounds OC gate is leaky (default-off, fail-open, or forgeable label). Out-of-bounds is not aspirational — it's a description of what currently works.

---

## 4. PseudoOperator: what formalization means

The machinery exists. Each controller has: a session loop, backend cooldown/fallback, CL anchoring, adaptive delay, and an investigate→fix→relaunch cycle. It just exists as two hardcoded copy-paste files.

There is already a declarative config schema that looks like PseudoOperator:
- `VF/.context/config.yaml` declares `watchers:` / `workers:`
- `OperationsCenter/.console/workers.yaml` exists

But both are inert. CLConfig.LoopConfig (`ContextLifecycle/src/context_lifecycle/models/config.py:22-32`) parses exactly one field (checkpoint_on_stop). Everything else lands in `extra="allow"` and no code reads it. VF's declared `relaunch_command` script doesn't even exist. There is no `PseudoOperator` concept anywhere (grep = 0).

### What formalization delivers

1. **De-duplicate the controller.** Extract `tools/loop/controller.py` into a single config-parameterized engine (a new shared library, or a canonical copy in one repo that the other installs). Parameters: `repo_root`, `model`, `session_prompt_path`, `max_cycles`, `failure_cap`, `timeout`, `schedule`, `require_human_trigger`.

2. **Activate the inert config schema.** Make CLConfig.LoopConfig (or a new PseudoOperatorConfig) a real consumer of the declared `workers`/`watchers` fields. Per-repo config homes:
   - VF: `VF/.context/config.yaml`
   - OC-system: `PlatformManifest/.console/pseudo_operator.yaml` or `OperationsCenter/.console/`

3. **Move guardrails from prompt to controller.** Cycle counter, failure counter, confidence floor (if measurable), and hard stop must be enforced in controller code. Prompt-prose becomes advisory.

4. **Formalize the "away/lazy" trigger semantics.** PseudoOperator runs when the operator is absent. This means: no manual intervention in the past N minutes, no active operator session, and/or an explicit enable flag. The controller should check this condition before spawning.

5. **No-self-rewrite invariant.** The controller must not be able to modify its own config without a human-signed update. Enforce via the restorer (see below) — not via prompt.

### What PseudoOperator does NOT do

- It does not unify VF and OC into one system. They have different targets, different session prompts, different cadences. The shared thing is the engine, not the fleet.
- It does not add the restorer or anchor — those are the next layer. PseudoOperator is the prerequisite.

---

## 5. Restorer: what it means in the live plane

Once PseudoOperator has a real config schema, a restorer can enforce a signed reference against it:

1. Operator signs a `pseudo_operator.yaml` (ed25519, same key infrastructure as the EVAL corpus).
2. A small restorer process (not the fleet, not the controller) periodically verifies the live config against the signed reference and re-deploys if they diverge.
3. The restorer is the **only writer** of live PseudoOperator config. Drift (any divergence) triggers restore. Intentional change requires a new operator signature.
4. The restorer itself cannot modify the signed reference — its write-path ends at the live config, not at the reference.

This makes "restore vs. change" decidable without an intent-classifier: restore means unauthorized divergence; change means the operator signed a new reference.

The restorer is not the anchor. The anchor (the ed25519 keypair, CODEOWNERS, the signing ceremony) is out-of-bounds — the fleet cannot reach it. The restorer is in-bounds but write-limited.

**Sequencing dependency:** restorer only pays off after PseudoOperator exists. There is nothing to restore-to until the config schema is real.

---

## 6. Build sequencing

Three independent tracks; one is urgent:

| Track | Scope | Dependency | Urgency |
|---|---|---|---|
| **A: Fix the 🔴 defects** | Forgeable label bypass, scope-check gap, fail-open containment, token in sandbox, VF timeout/locking, `audit_dispatch` timeout | None — standalone targeted PRs | **Now** — live risk independent of reorg |
| **B: PseudoOperator** | De-dup controllers, activate config schema, move guardrails into code, formalize trigger semantics | A (some defects touch the same files) | Medium — enables the next track |
| **C: Restorer + live-plane anchor** | Signed config reference, restorer process, no-self-rewrite invariant | B (needs a real config to restore to) | Later — only useful after B |

Track A is a set of small targeted PRs against OperationsCenter (and one against VF). None requires a reorg. Do them first.

Track B is a medium refactor: a new shared library or canonical controller, config schema activation, and guardrail migration. One PR per logical step.

Track C is the genuinely new architecture. Don't start it until B is stable and running.
