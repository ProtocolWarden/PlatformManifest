# Sandbox Token Hardening Spec

**Status:** backlogged — not yet implemented  
**Priority:** high (live risk; token in least-trusted agent env)

## Problem

The OC board worker injects the full `GITHUB_TOKEN` (a long-lived OAuth `gho_` token) directly into the bwrap sandbox environment via `--setenv` (`board_worker/_subprocess.py:172`). This token:

- Is **write-capable** across every repo the credential owns.
- **Never expires** (static OAuth token, valid until explicitly revoked).
- Lands in the **least-trusted agent's process env** — the thing that runs arbitrary LLM-generated code.

If the sandbox is compromised (sandbox escape, prompt injection, malicious PR code executed by the reviewer), the attacker holds a persistent write credential to all owned repos.

The egress proxy (`oc-egress-proxy.service`) is separately hardening the network surface but does not address the credential itself.

## Desired properties

1. The credential injected into the sandbox must be **scoped to the minimum required** (read commits + push one branch + open one PR on one repo per task).
2. The credential must be **short-lived** — useless after the task finishes (target: ≤ 1 hour TTL).
3. The credential must be **non-renewable** from inside the sandbox — the sandbox cannot request a new token.
4. The board worker's long-lived credential must **not be readable from inside the sandbox** at any point.

## Approach: GitHub App installation token

Replace the OAuth token with a per-task GitHub App installation token:

1. **Register a GitHub App** scoped to the repos OC writes (ProtocolWarden org or explicit repo list). Grant: `contents: write`, `pull_requests: write`, `checks: read`. Nothing else.
2. **Store the App private key** outside the OC process (e.g., in a secrets store or as a file path in `operations_center.local.yaml` that is never forwarded to the sandbox).
3. In `board_worker/_subprocess.py`, before spawning the sandbox:
   - Call GitHub API: `POST /app/installations/{id}/access_tokens` with `repositories: [task_repo]` and `permissions: {contents: write, pull_requests: write}`.
   - Pass the returned installation token (`ghs_…`, 1-hour TTL) as `GIT_CONFIG_PARAMETERS` or a `Authorization: Bearer` header in a per-process git config — **not as a raw env var**.
4. After the sandbox exits, **do nothing** — the token expires on its own.

The board worker's App private key never enters the sandbox. The sandbox gets a token that expires in ≤ 1 hour and is scoped to exactly one repo.

## Alternative: fine-grained PAT (simpler, weaker)

If registering a GitHub App is too much friction:

- Replace `gho_` with a **fine-grained PAT** scoped to specific repos + `contents: write` + `pull_requests: write` only.
- Fine-grained PATs support expiry (set to 30 or 90 days).
- Not per-task-ephemeral, but eliminates org-wide write scope and reduces TTL from "never" to weeks.
- Upgrade path: start here, migrate to App token later.

## Injection change

Current (`_subprocess.py:172`):
```python
env["GITHUB_TOKEN"] = os.environ["GITHUB_TOKEN"]
```

Target (App token path):
```python
token = _acquire_installation_token(repo=task_repo, ttl=3600)
env["GIT_CONFIG_COUNT"] = "1"
env["GIT_CONFIG_KEY_0"] = "http.https://github.com/.extraheader"
env["GIT_CONFIG_VALUE_0"] = f"Authorization: Basic {_b64(token)}"
# GITHUB_TOKEN never forwarded
```

This is the same pattern the GitHub Actions runner uses — the raw PAT never touches the subprocess env; only the derived git header does.

## What this does NOT fix

- Fail-open containment (bwrap/netns/egress off-by-default) — separate item.
- Forgeable `source: autonomy` label bypass — separate item.
- Executor timeout missing — separate item.

## Sequencing

This is a standalone fix — no dependency on PseudoOperator or the restorer work. Can ship as a single targeted PR against OperationsCenter before any reorg.

Files to touch: `board_worker/_subprocess.py`, `config/settings.py` (add github_app_id / github_app_key_path fields), optionally `operations_center.example.yaml`.
