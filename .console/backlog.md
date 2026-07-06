# Backlog

_Durable work inventory — broader than the current task, narrower than a full backlog._
_Update after each meaningful chunk of progress. Keep it short and actionable._

## In Progress

_(idle — reconciliation + role-generalization arcs complete)_

## Up Next

- [ ] **[OPERATOR] Anchoring ceremony — the ONE human step** (anchors BOTH the
      EVAL corpus and the loop configs with one key): (1) offline
      `python -m operations_center.eval.sign keygen --private-out operator_priv.pem`,
      keep the private key off-infra; (2) paste the pubkey hex into
      `OperationsCenter/eval/constitution/operator_pubkey.ed25519`,
      `OperationsCenter/.console/operator_pubkey.ed25519`, and
      `VideoFoundry/.context/operator_pubkey.ed25519` (all placeholders,
      CODEOWNERS-pinned); (3) `cl loop sign-config --config <repo cfg> --key
      operator_priv.pem` in OC + VF, commit the `.signed.json`/`.sig`;
      (4) add `--require-signed` to `operations-center.sh loop_start` and
      `vf.sh loop_start`. Until then `cl loop run` runs in loud unsigned mode.

- [ ] **FLEET RESTART PREREQUISITES** (when the operator resumes the fleet):
      (1) add the fleet's Plane service account to
      `task_admission.trusted_label_authors` in operations_center.local.yaml
      (else autonomy lane routes through normal review — safe degrade);
      (2) optionally register a GitHub App + set `git.github_app_id` /
      `git.github_app_key_path` (else long-lived-token warning);
      (3) containment is now required-by-default — bwrap/pasta/proxy breakage
      fails tasks visibly;
      (4) provisioning must install ContextLifecycle v0.4.1 into the OC venv
      (the loop is now `cl loop run`; local venv holds an editable CL).
      Resume: start oc-egress-proxy, then oc-fleet.

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

