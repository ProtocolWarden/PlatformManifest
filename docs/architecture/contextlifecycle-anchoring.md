# ContextLifecycle anchoring & ContextGuard enforcement

How every Claude/Codex/Aider session in this ecosystem gets *anchored* to its
owning manifest, and how `cl` is reliably located across the very different
execution contexts that launch those sessions.

This is the cross-cutting design behind the wrappers, hooks, loop controllers,
and provisioning scripts. If you touch any code that launches a CLI or runs
`cl`, read this first.

---

## The two variables

| Variable | Kind | Lifetime | Set by | Lives where |
|----------|------|----------|--------|-------------|
| `CL_HOME` | **machine state** | permanent | provisioning | the local clone path of ContextLifecycle (`$CL_HOME/bin/cl`) |
| `CL_ANCHOR` | **session state** | per session | `cl session start` | the owning manifest of the current repo (resolved via RepoGraph) |

- `CL_HOME` differs per machine, so it **cannot live in a repo**. It is recorded
  by `provision-machine.sh` into `~/.bashrc` and `~/.claude/settings.json`.
- `CL_ANCHOR` (+ `CL_SESSION_ID`) is produced by `cl session start`, which maps
  the current working directory to its manifest through the RepoGraph registry
  and emits eval-able `export` lines. It must be present **in the CLI's process
  environment before the CLI launches** — it cannot be set afterward.

ContextGuard (the `pre_tool_use` hook) blocks every tool call when `CL_ANCHOR`
is unset. So the entire job of the launch machinery is: *resolve `cl`, run
`cl session start`, and put `CL_ANCHOR` into the environment before exec'ing the
CLI.*

---

## Why finding `cl` is the hard part

Sessions launch from wildly different shells:

| Context | Sources `~/.bashrc`? | Reads `settings.json`? | Has `CL_HOME`? |
|---------|:---:|:---:|:---:|
| Interactive terminal | yes | — | yes |
| Claude Code's own process | — | yes (Claude loads it) | yes |
| **Zellij pane** (console-launched) | **no** | **no** | **no** |
| **systemd / cron** | **no** | **no** | **no** |
| `nohup` from an interactive shell | no | no | inherited (yes) |

Most `~/.bashrc` files begin with `[[ $- != *i* ]] && return`, so
`source ~/.bashrc` is a **no-op in non-interactive shells**. That is the root
cause of every "Blocked — CL_ANCHOR not set" incident: the launch shell could
not find `cl`, `cl session start` silently failed, and the session ran
unanchored.

### The canonical resolution order

Every consumer resolves `cl` the same way, and **never** relies on `source
~/.bashrc`:

```
1. $CL_HOME/bin/cl            (CL_HOME from the environment)
2. ~/.claude/settings.json    (env.CL_HOME — machine-provisioned, readable
                               from non-interactive contexts)
3. `cl` on PATH               (shutil.which / command -v)
```

`settings.json` is the key fallback: it is the one machine-provisioned source
that a non-interactive process can read without a login shell.

---

## Where each consumer resolves `cl`

### 1. OperatorConsole panes — bake the path at generation time
`OperatorConsole/src/operator_console/bootstrap.py`

The console process is launched from an interactive terminal, so it already has
`CL_HOME`. It resolves `cl` **once, in Python** (`_resolve_cl_bin()`, same
order as above) and **bakes the literal absolute path** into the wrapper script
it writes to `/tmp` for each pane:

```bash
# ContextLifecycle: anchor at owning manifest (cl path baked at launch).
_CL_BIN='/abs/path/to/ContextLifecycle/bin/cl'
eval "$("$_CL_BIN" session start 2>/dev/null || true)"
```

No resolution happens inside the (non-interactive) pane shell — the path is a
literal, determined when you ran `console open`. The post-claude drop-to-shell
`claude()` function bakes the same path so typing `claude` again re-anchors.

### 2. Loop controllers — external `tools/`
`OperationsCenter/tools/loop/controller.py` (and the equivalent loop controller
in tenant workspace repos)

These are Python daemons (launched by `nohup`, or a systemd unit). They resolve
all external commands through `_resolve_command(name)`, which tries `PATH` then
`_fallback_command_candidates(name)`. The `cl` branch of that fallback walks the
canonical order including the `settings.json` read, so the controller anchors
even under systemd/cron where neither `CL_HOME` nor `cl`-on-PATH is present.

The controller anchors **once per loop run** (`_anchor_via_cl`, called from
`main()` before the iteration loop), merges `CL_ANCHOR`/`CL_SESSION_ID` into the
env it passes to every spawned session, and archives the session on shutdown
(`_end_cl_session`). Non-hook backends (codex, aider) additionally use
`cl context hydrate` / `cl context capture` at the session boundary; claude uses
the per-tool hooks instead.

### 3. OC executor backends — the per-dispatch hydrate/capture wrap
`OperationsCenter/src/operations_center/execution/cl_wrap.py` (ADR 0002 P4)

The two consumers above get the anchor *into the environment*; this is the
layer that makes executor-backend work actually use it. The execution
coordinator wraps **each backend dispatch** in `cl_dispatch_wrap(request)`:
it derives a lineage id from the work item (`run_id`/`proposal_id`, prefixed
`l-`), calls `cl.hydrate()` before the adapter runs and `cl.capture()` after —
**even on adapter exception**, so failed lineages still leave a trace under
the anchor manifest. Those captures are the `l-*.yaml` lease records that
accumulate in the anchoring manifest's `.context/sessions/<sid>/`.

Retention: loop/executor sessions never call `cl session end`, so lease
records accumulate until GC'd. The driver is **opportunistic auto-GC inside
`cl session start`** (throttled to once per 24h per anchor) — every host that
accumulates state eventually starts another session on the same anchor, so no
external scheduler is needed. The action is two-stage, chosen by adversarial
review (plain auto-delete loses still-live long-running sessions whose *id*
is old; warn-only is inert here — loop controllers swallow stderr):

1. **Move (reversible):** sessions older than 14 days move to
   `.context/archived/` with a `.gc-moved-at` stamp. A still-live writer
   self-heals — its next capture recreates the `sessions/` dir.
2. **Delete (bounded):** archived dirs are deleted 30 days after the stamp,
   bounding total session state at ~44 days. Deletion is safe by the
   ephemeral-tier invariant — a session file must never hold the only copy
   of anything worth keeping.

Actions are logged to `sessions/.gc/log`. Manual sweeps remain available via
`cl session prune [MANIFEST] --retain-days N` (dry-run unless `--apply`; the
current `$CL_SESSION_ID` always survives).

The wrap is opt-in by environment and triple-guarded no-op when:

- `CL_ANCHOR` is unset (nothing anchored the launching process), or
- `context_lifecycle` is not importable, or
- hydrate raises `AnchorMissing` / `SessionNotStarted`.

So an executor backend never resolves `cl` itself — it inherits the anchor
from whatever launched OC (the loop controller's once-per-run anchor, or an
OperatorConsole pane's baked prelude), and silently runs un-instrumented when
nothing did. Unanchored tests pass unchanged for the same reason.

### 4. Committed ContextGuard hooks — the enforcement point
`<repo>/.claude/hooks/pre_tool_use.sh` + `stop.sh`, wired by `<repo>/.claude/settings.json`

The 9-line executor shim resolves `cl` (`CL_HOME` → PATH) and delegates to the
canonical engine: `exec "$CL_BIN" hook pre_tool_use "$@"`. The hook
subprocess inherits Claude Code's process env, which carries `CL_HOME` (from
`settings.json`) and `CL_ANCHOR` (set by the launch wrapper) — so the shim's
simpler `CL_HOME → PATH` resolution is sufficient here.

Repos with committed hooks: PlatformManifest (full adapter), OperationsCenter,
OperatorConsole, TeamExecutor, CritiqueExecutor; DAGExecutor gets the shim
installed by provisioning. Hook presence is verified each provision by the
"Hook health" step.

### 5. Provisioning — where `CL_HOME` is recorded
`PlatformManifest/scripts/provision-machine.sh`

Writes `CL_HOME` into both `~/.bashrc` (interactive shells) and
`~/.claude/settings.json` (Claude Code + the non-interactive fallback above),
registers manifests in RepoGraph (so `cl session start` can resolve anchors),
installs/verifies hooks, and smoke-tests that `cl session start` resolves the
expected anchor from each key repo.

---

## Enforcement model (hook exit codes)

`cl hook pre_tool_use` and the shim use Claude Code's hook exit-code contract:

| Exit | Meaning | Effect on tool call |
|:----:|---------|---------------------|
| `0` | anchored & allowed | proceeds |
| `2` | `CL_ANCHOR` unset / invalid (engine blocks) | **blocked**, reason shown to Claude |
| `1` / other | shim couldn't find `cl` | **non-blocking** warning; tool proceeds |

This produces a deliberate **bootstrap-safe** property:

- **Fresh clone, `cl` not yet installed** → shim exits `1` → non-blocking → you
  can still run tools to provision the machine. *No self-lockout.*
- **Provisioned but unanchored** → engine exits `2` → blocked. This is real
  enforcement, and it only activates once `cl` exists — i.e. exactly when you
  can fix it with `cl session start`. The block never precedes the cure.
- **Anchored** (the normal console-launched path) → exits `0`.

Bootstrap (`setup.sh`, `provision*.sh`) runs through a shell, not Claude, so it
is never gated by the hook regardless.

---

## Quick diagnosis

`Blocked — CL_ANCHOR not set` inside a session means the launch path failed to
anchor. Check, in order:

1. `echo $CL_ANCHOR` in the session — empty confirms it.
2. Is `cl` resolvable? `"${CL_HOME:-$(python3 -c "import json,pathlib;print(json.loads((pathlib.Path.home()/'.claude/settings.json').read_text()).get('env',{}).get('CL_HOME',''))")}"/bin/cl --help`
3. Does `cl session start` from the repo emit `CL_ANCHOR`? If not, the repo
   isn't registered — `repograph manifest add <manifest>` (or re-run
   `provision-machine.sh`).
4. Was the session launched outside the console wrappers (a bare `cd repo &&
   claude`)? Then nothing ran `cl session start` — use the console, or
   `eval "$(cl session start)"` first.
