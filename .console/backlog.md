# Backlog

_Durable work inventory — broader than the current task, narrower than a full backlog._
_Update after each meaningful chunk of progress. Keep it short and actionable._

## In Progress

_(idle — reconciliation + role-generalization arcs complete)_

## In Progress (see below — Up Next reordered)

- [ ] **[OC/VF] Track B: PseudoOperator formalization** — de-dup the two
      copy-paste `tools/loop/controller.py` files into one config-parameterized
      engine; activate the inert `workers`/`watchers` config schema
      (CLConfig.LoopConfig currently parses one field); away/lazy trigger
      semantics. Per-repo config: VF → `.context/config.yaml`, OC-system →
      `PlatformManifest` or `OperationsCenter/.console/`.
      (VF guardrail caps already moved into controller code by Track A7.)

- [ ] **[OC/VF] Track C: Restorer + live-plane anchor** — ed25519-signed
      pseudo_operator config reference; restorer as the sole writer of live
      config; no-self-rewrite invariant. Depends on Track B.
      Spec: `docs/architecture/oc-audit-and-pseudooperator-spec.md` §5.

- [ ] **FLEET RESTART PREREQUISITES** (when the operator resumes the fleet):
      (1) add the fleet's Plane service account to
      `task_admission.trusted_label_authors` in operations_center.local.yaml
      (else autonomy lane routes through normal review — safe degrade);
      (2) optionally register a GitHub App + set `git.github_app_id` /
      `git.github_app_key_path` (else long-lived-token warning);
      (3) containment is now required-by-default — bwrap/pasta/proxy breakage
      fails tasks visibly. Resume: start oc-egress-proxy, then oc-fleet.

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

