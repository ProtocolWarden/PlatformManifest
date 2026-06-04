# Backlog

_Durable work inventory — broader than the current task, narrower than a full backlog._
_Update after each meaningful chunk of progress. Keep it short and actionable._

## In Progress

_(idle — reconciliation + role-generalization arcs complete)_

## Up Next

- [ ] Phase 6 of the private-manifest role generalization (lexical scrub-target
      enforcement) — BLOCKED on an operator decision: the repo instance is named
      identically to the manifest-type vocabulary (ontology class / schema title),
      so the name can't be banned without renaming the instance repo first.
      See design doc §7 / Status note.
- [ ] Optional: converge the `.console/reconcile.yaml` worksheet format (still
      the interim schema-1 shape; works fine).

## Done

- [x] 2026-06-04 — Private-manifest role generalization phases 1–5 executed
      fleet-wide (shared resolver, hooks, provisioning, source/tests, docs).
- [x] 2026-06-04 — R2-in-CI on all 19 public repos (last 6 audit workflows
      added); B64 secret rotation script (`scripts/bootstrap-boundary-secrets.sh`).
- [x] 2026-06-04 — `.console/` reconciliation arc complete (prune + scrub +
      enforce on all 19 public repos; status dashboard generated).
