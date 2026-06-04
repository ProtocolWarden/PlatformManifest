# `.context/` Layout — PlatformManifest as Cognition Host

_Status: P3 of work order `PlatformDeployment/docs/architecture/adr/0002-work-order-manifest-cognition.md`._

PlatformManifest hosts durable cognition state for any session anchored to it (`CL_ANCHOR=<this repo>`). Consumer repos (OperationsCenter, executors, etc.) carry no `.context/` of their own; they fire CL hooks that read and write here.

## Layout

```
PlatformManifest/.context/
  sessions/                     # per-session state (created at runtime)
    s-<YYYY-MM-DD>-<rand>/      # CL_SESSION_ID
      active/                   # lineage-scoped InvestigationCapsules
      checkpoints/              # LoopCheckpoints (ISO-8601 UTC filenames)
      handoffs/                 # WorkerHandoff records
  archived/                     # ended sessions (moved by `cl session end`)
  templates/                    # shared schemas
    investigation_capsule.template.yaml
    worker_handoff.template.yaml
    loop_checkpoint.template.yaml
  config.yaml                   # manifest-wide CL guard config
```

## Lifecycle

1. **Session start** — operator runs `eval $(cl session start PlatformManifest)`. CL sets `CL_ANCHOR` and `CL_SESSION_ID`, creates `sessions/<sid>/{active,checkpoints,handoffs}/`.
2. **During session** — CL hooks (pre_tool_use, stop) read `config.yaml` for guard flags and walk the session subdir for active capsules/handoffs/checkpoints. RepoGraph authorizes every write against the anchor's visibility scope (PM = public; cannot host capsules referencing private-owned repos).
3. **Session end** — `cl session end` moves `sessions/<sid>/` to `archived/<sid>/`. Archived sessions are git-tracked.

## Scope

PM is **public-scoped** (`visibility_scope: public` in `platform_manifest.yaml`). Per the RepoGraph authorization rules (ADR 0002 P0.4), a PM-anchored session may host cognition referencing:

- Repos owned by PM (e.g. OperationsCenter, ContextLifecycle, TeamExecutor).
- Repos in any other public manifest (none today).

It **cannot** host cognition referencing private-owned repos. For those, anchor to the private-manifest repo (or the relevant private project manifest) instead. Misuse is a hard error from RepoGraph at hook time, not a silent leak.

## Templates

The three templates here are public-safe (no private repo names, no private-scope metadata). Consumer-side dispatchers populate `worker_scope.repo` and similar fields at handoff creation time.

## What does NOT live here

- Per-consumer-repo operational config (worker definitions, watchdog cycle settings, relaunch commands). Those live in the consumer repo's `.console/` (e.g. `OperationsCenter/.console/workers.yaml`).
- Per-machine state (runtime locks, schedule files). Those stay in the consumer repo's `logs/local/` or `.console/`.
- Live cognition for private projects. Use the private-manifest repo.

## Related

- Work order: `PlatformDeployment/docs/architecture/adr/0002-work-order-manifest-cognition.md` (P0.5 layout, P3 host setup).
- CL CLI: `ContextLifecycle/` (≥ v0.2.0; reads from `CL_ANCHOR`-resolved manifest).
- RepoGraph: `RepoGraph/` (≥ v0.2.0; `can_anchor_host()` enforces visibility).
