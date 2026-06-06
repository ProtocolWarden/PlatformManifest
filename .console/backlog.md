# Backlog

_Durable work inventory — broader than the current task, narrower than a full backlog._
_Update after each meaningful chunk of progress. Keep it short and actionable._

## In Progress

_(idle — reconciliation + role-generalization arcs complete)_

## Up Next

- [ ] **On the OTHER host (one-time):** run `scripts/provision-machine.sh` —
      pulls ContextLifecycle to current (PM #72 added the pull step), which
      activates session auto-GC (CL #24/#25) on that host's PM/PrivateManifest
      anchors. Optional immediate cleanup of the lease backlog there:
      `cl session prune <anchor> --apply` (dry-run first without `--apply`).
      Delete this item once done. _(This host: already done 2026-06-06.)_

- [ ] Optional: converge the `.console/reconcile.yaml` worksheet format (still
      the interim schema-1 shape; works fine).

## Done

- [x] 2026-06-04 — FLEET GREEN: pre-existing red main CI fixed on all 19 public
      repos (incl. first-ever green semantic-federation run; gate policy synced
      to the 18-repo public set).

- [x] 2026-06-04 — Phase 6 closed as not-needed (operator: the instance name is
      not secret, only contents; architectural enforcement stands). Generalization
      effort COMPLETE.

- [x] 2026-06-04 — Private-manifest role generalization phases 1–5 executed
      fleet-wide (shared resolver, hooks, provisioning, source/tests, docs).
- [x] 2026-06-04 — R2-in-CI on all 19 public repos (last 6 audit workflows
      added); B64 secret rotation script (`scripts/bootstrap-boundary-secrets.sh`).
- [x] 2026-06-04 — `.console/` reconciliation arc complete (prune + scrub +
      enforce on all 19 public repos; status dashboard generated).
