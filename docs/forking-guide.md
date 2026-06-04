# Forking guide — bootstrapping your own private overlay

This guide is for someone who has forked PlatformManifest (or the broader
ProtocolWarden ecosystem) and wants to operate their own private projects
without leaking private repo names into public CI.

## Why a private overlay exists

PlatformManifest is the public source of truth for the platform repo map —
the public repos, their kinds, and their public-safe relationships. If you
want to layer **private projects** (managed projects, private infrastructure,
private aliases) on top of that public base, you create a **private-manifest**
repo. It carries:

- Private repo identities (canonical names, aliases, visibility flags)
- Private-only relationships (e.g., "managed by", "deployed to")
- Disclosure/projection rules for each entity

The private-manifest repo is a *private GitHub repo*. It never appears publicly. But
public CI (Custodian audits) needs to know which names are forbidden in public
code, without seeing the full private graph. That's the **boundary artifact**:
a small JSON document that lists `forbidden_names` and provenance metadata,
derived from the private-manifest repo by RepoGraph's `build_boundary_artifact()`.
It exposes only the negative space ("don't write these names in public code"),
not the relationships or descriptions.

## Step-by-step bootstrap

### 1. Create your private-manifest repo

Create a new **private** GitHub repository under your account or org. The
layout mirrors the reference private-manifest repo:

```
<private-manifest-repo>/
├── graph/
│   ├── repos.yaml                      # private repo identities
│   ├── edges.yaml                      # private relationships
│   └── projection_profiles.yaml        # disclosure modes
├── manifests/
│   └── <project>/private_manifest.yaml # per-project overlay (optional)
├── src/private_manifest/
│   └── export_boundary_artifact.py     # generator (copy from reference)
├── scripts/
│   └── export_private_repo_names.py    # CLI entry
└── boundary/
    └── boundary_disclosure_artifact.json  # generated, committed
```

The minimum viable private-manifest repo is `graph/repos.yaml` listing every private
repo (visibility=private, kind=ManagedProject or similar) and `graph/edges.yaml`
listing private relationships. See `examples/private_repos_minimal.yaml` in
the reference repo for the schema.

### 2. Add the publish-boundary workflow

Copy `.github/workflows/publish-boundary.yml` from the reference private-manifest repo.
On every push to `main` that touches `graph/` or the generator, it:

1. Installs RepoGraph from git
2. Runs `python -m private_manifest.export_boundary_artifact --graph-root graph --out boundary/boundary_disclosure_artifact.json --source-graph-id <your-graph-id> --source-ref-or-commit "$GITHUB_SHA"`
3. Commits the regenerated artifact back to `main` if it changed

Required workflow permission: `contents: write`.

Run the generator locally once before pushing to seed the initial artifact —
otherwise downstream CI 404s on the first run.

### 3. Generate a fine-grained PAT

In GitHub settings → Developer settings → Personal access tokens → Fine-grained
tokens, create a token with:

- **Resource owner**: the account/org that owns your private-manifest repo
- **Repository access**: *Only select repositories* → your private-manifest repo, nothing else
- **Repository permissions**: `Contents` → **Read-only**
- **Expiration**: 1 year (set a calendar reminder to rotate)

**This token is the entire access control surface.** Anyone with it can read
your full `forbidden_names` list, which is itself sensitive (it discloses that
your private projects exist, by name). Do not commit it. Do not paste it into
chat, logs, or PR descriptions. If it ever leaks, revoke immediately.

### 4. Set secrets in every consuming repo

Each public repo that runs the `custodian-audit` workflow needs two repository
secrets:

| Secret name | Value |
|---|---|
| `PRIVATEMANIFEST_READ_TOKEN` | the fine-grained PAT from step 3 |
| `REPOGRAPH_BOUNDARY_ARTIFACT_FILE` | `https://raw.githubusercontent.com/<owner>/<private-manifest-repo-name>/main/boundary/boundary_disclosure_artifact.json` |

If you're on a **GitHub organization**, set these once as *organization
secrets* and scope them to the consuming repos. Single source, free tier
includes this.

#### Personal-account tutorial: `scripts/bootstrap-boundary-secrets.sh`

If you're on a **personal account**, there are no org-level secrets. This
repo ships a script that sets both secrets across every consuming repo in
one pass and shreds the local PAT file when it's done.

**Step 4.1 — Write the PAT to a temp file with no trailing newline.**

Two safe ways. Pick one.

Option A — interactive prompt, no shell-history record of the token:

```bash
read -s -p 'PAT: ' p && printf '%s' "$p" > /tmp/pat && unset p && echo
```

Option B — direct write (only safe in a private terminal session):

```bash
printf '%s' 'github_pat_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx' > /tmp/pat
```

Avoid `echo "..." > /tmp/pat` — it appends a trailing newline that breaks the
token. Always `printf '%s'`.

**Step 4.2 — Run the bootstrap script.**

```bash
./scripts/bootstrap-boundary-secrets.sh \
    --owner <your-github-username> \
    --token-file /tmp/pat
```

By default, the script targets the platform's reference list of consumer
repos and reads the artifact from
`<owner>/<private-manifest-repo-name>/main/boundary/boundary_disclosure_artifact.json`.
Use `--private-repo`, `--branch`, `--artifact-path`, or `--repos-file` to
point at a different layout.

**Step 4.3 — Verify shredding.**

The script registers an `EXIT` trap that runs `shred -u /tmp/pat` on success
**and on failure** (Ctrl-C, network errors, anything). If you see `Token file
shredded.` at the end, you're clean. If the script was killed before the trap
fired, run `shred -u /tmp/pat` manually. To verify the file is gone:

```bash
test -f /tmp/pat && echo "STILL THERE — shred manually" || echo "clean"
```

**Step 4.4 — Confirm secrets propagated.**

```bash
gh secret list --repo <owner>/<one-of-the-consumer-repos>
```

You should see `PRIVATEMANIFEST_READ_TOKEN` and `REPOGRAPH_BOUNDARY_ARTIFACT_FILE`
with recent timestamps.

**Rotation.**

When the PAT expires (annual) or after a suspected leak: revoke the old PAT
in GitHub settings, generate a new one with the same scope, then re-run the
same script with the new token file. Old secret values are overwritten
in-place; no per-repo cleanup needed.

**Why a script and not just a copy-pasted loop?**

The script:
- Validates the token file is non-empty before sending anything to GitHub
- Shreds the file on **any** exit path (success, error, Ctrl-C) via a trap —
  more reliable than a manual `shred` at the end of a loop
- Supports `--dry-run` so you can preview what would be set before any
  network call
- Reports which repo failed if `gh secret set` errors out (rare, but useful)

### 5. Confirm the audit gate works

Open a PR on any consuming repo. The `custodian-audit` workflow should:

1. Print `boundary_provenance=<your-graph-id>@<commit-sha>` in the
   "Materialize boundary artifact file" step
2. Run `custodian-multi` and either pass clean or surface findings

If the materialize step prints `::warning::REPOGRAPH_BOUNDARY_ARTIFACT_FILE
secret unset — skipping custodian audit`, the secret didn't propagate — check
`gh secret list --repo <owner>/<repo>`.

## How the artifact stays fresh

There is **no background sync**. Each CI run fetches the current artifact from
your private-manifest repo's `main` branch via the raw GitHub URL. Whenever you
update `graph/`, the `publish-boundary` workflow regenerates and commits the
artifact within seconds; the next consumer CI run immediately sees the new
forbidden names. No drift window, no per-repo rotation.

## Multi-tenant note

The boundary artifact contains the **union** of all private names in your
private-manifest repo. If you host private overlays for multiple unrelated tenants
in the same private-manifest repo, every consumer sees every tenant's
forbidden names. If that's a concern, run **one private-manifest repo per tenant**
and configure each consuming repo with the appropriate URL.

The decision to ship single-tenant today and the binding migration plan to
multi-tenant are documented in
[`PlatformDeployment/docs/architecture/adr/0003-boundary-artifact-tenancy-model.md`](https://github.com/ProtocolWarden/PlatformDeployment/blob/main/docs/architecture/adr/0003-boundary-artifact-tenancy-model.md).
Read it before adding a second tenant or before designing per-project
cognition anchoring — the ADR captures which pieces are already
multi-tenant-ready (the artifact schema and generator) and which still need
work (Custodian multi-artifact union, ContextLifecycle per-project
anchoring, per-tenant secret routing in bootstrap tooling).

## Threat model summary

| Threat | Mitigation |
|---|---|
| PAT leaks via compromised CI workflow | PAT is read-only, scoped to one private repo; rotate annually |
| Boundary artifact JSON appears in public CI logs | Materialize step writes to `$RUNNER_TEMP` and only prints provenance line; secrets are masked in GitHub Actions logs |
| Private names leak via PR diff in a public consumer repo | That's exactly what the audit gate catches — `B1` detector scans for any `forbidden_names` in tracked files |
| private-manifest repo unavailable at fetch time | Audit fails closed (CI red); old artifact remains readable from the last commit, so transient outages don't break things |
| Old PAT remains valid after rotation | Fine-grained PATs are independent; revoke the old one explicitly in GitHub settings |

## Reference implementation

The ProtocolWarden ecosystem is the reference implementation. The relevant
repos are public except where noted:

- `ProtocolWarden/PlatformManifest` — public base
- the private-manifest repo — private overlay (private repo)
- `ProtocolWarden/RepoGraph` — schema + generator library
- `ProtocolWarden/Custodian` — boundary artifact consumer (B1/B2 detectors)

See `docs/architecture/public_private_projection.md` for the projection
semantics and `docs/architecture/visibility_boundary.md` for how visibility
is enforced across the ecosystem.
