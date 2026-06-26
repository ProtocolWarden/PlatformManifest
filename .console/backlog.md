# Backlog

_Durable work inventory — broader than the current task, narrower than a full backlog._
_Update after each meaningful chunk of progress. Keep it short and actionable._

## In Progress

_(idle — reconciliation + role-generalization arcs complete)_

## Up Next

- [ ] **[OC] Sandbox token hardening** — replace long-lived OAuth `gho_` token
      forwarded into bwrap sandbox with a per-task GitHub App installation token
      (1h TTL, repo-scoped, raw credential never in sandbox env). Fine-grained
      PAT is the low-friction first step. Spec:
      `docs/architecture/sandbox-token-hardening-spec.md`.
      Touch: `board_worker/_subprocess.py`, `config/settings.py`.

- [ ] **[OC] Remaining 🔴 audit defects** (post-pause, pre-restart):
      (a) forgeable `source: autonomy` label skips policy gates (`engine.py:521`);
      (b) fail-open containment — bwrap/netns/egress off-by-default (`sandbox.py`);
      (c) executor timeout missing on board path (`_subprocess.py:337`);
      (d) `audit_dispatch` timeout=None hangs OC on wedged VF audit.
      Each is a small targeted PR, no reorg dependency.

- [ ] **[OC/VF] PseudoOperator formalization** — de-dup the two copy-paste
      `tools/loop/controller.py` files into one config-parameterized engine;
      activate the inert `workers`/`watchers` config schema (CLConfig.LoopConfig
      currently parses one field); move VF guardrails out of prompt-prose into
      controller. Per-repo config: VF → `.context/config.yaml`, OC-system →
      `PlatformManifest` or `OperationsCenter/.console/`.

- [ ] **On the OTHER host (one-time):** run `scripts/provision-machine.sh` —
      pulls ContextLifecycle to current (PM #72 added the pull step), which
      activates session auto-GC (CL #24/#25) on that host's PM/PrivateManifest
      anchors. Optional immediate cleanup of the lease backlog there:
      `cl session prune <anchor> --apply` (dry-run first without `--apply`).
      Delete this item once done. _(This host: already done 2026-06-06.)_

- [ ] Optional: converge the `.console/reconcile.yaml` worksheet format (still
      the interim schema-1 shape; works fine).

## Done

_Completed items archived._

