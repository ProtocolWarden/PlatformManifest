<!-- Leaf doc: provisioning script conventions. -->

## Inject

- **Idempotent or it's broken.** Every provisioning step must be safe to re-run.
  `_ensure_venv` re-runs `pip install -e` every time (so a dependency-changing
  `git pull` is picked up) — follow that pattern, don't gate work behind
  "already exists" checks that hide drift.
- **Hooks/subprocesses don't source `~/.bashrc`.** Non-interactive shells (Claude
  Code hook subprocesses, loop controllers) won't pick up `~/.bashrc`. Wire
  `CL_HOME` into BOTH `~/.bashrc` AND `~/.claude/settings.json` env so `cl`
  resolves for hook subprocesses.
- **Exit-code contract:** hooks use `2 = block`, `1 = non-blocking warn`,
  `0 = allow`. A fresh clone must stay bootstrap-safe — never hard-fail a hook on
  missing optional state.
- **Order matters:** `provision.sh` chains clone-repos → provision-machine; CL+RG
  must be cloned before provision-machine needs them.

## Reference

`docs/architecture/contextlifecycle-anchoring.md` covers `cl` resolution order
(CL_HOME → settings.json → PATH) and why `source ~/.bashrc` fails in
non-interactive shells.
