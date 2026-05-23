# Forking guide — bootstrapping your own private overlay

This guide is for someone who has forked PlatformManifest (or the broader
ProtocolWarden ecosystem) and wants to operate their own private projects
without leaking private repo names into public CI.

## Why a private overlay exists

PlatformManifest is the public source of truth for the platform repo map —
the public repos, their kinds, and their public-safe relationships. If you
want to layer **private projects** (managed projects, private infrastructure,
private aliases) on top of that public base, you create a **PrivateManifest**
repo. It carries:

- Private repo identities (canonical names, aliases, visibility flags)
- Private-only relationships (e.g., "managed by", "deployed to")
- Disclosure/projection rules for each entity

The PrivateManifest is a *private GitHub repo*. It never appears publicly. But
public CI (Custodian audits) needs to know which names are forbidden in public
code, without seeing the full private graph. That's the **boundary artifact**:
a small JSON document that lists `forbidden_names` and provenance metadata,
derived from the PrivateManifest by RepoGraph's `build_boundary_artifact()`.
It exposes only the negative space ("don't write these names in public code"),
not the relationships or descriptions.

## Step-by-step bootstrap

### 1. Create your PrivateManifest repo

Create a new **private** GitHub repository under your account or org. The
layout mirrors the reference at `ProtocolWarden/PrivateManifest`:

```
PrivateManifest/
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

The minimum viable PrivateManifest is `graph/repos.yaml` listing every private
repo (visibility=private, kind=ManagedProject or similar) and `graph/edges.yaml`
listing private relationships. See `examples/private_repos_minimal.yaml` in
the reference repo for the schema.

### 2. Add the publish-boundary workflow

Copy `.github/workflows/publish-boundary.yml` from the reference PrivateManifest.
On every push to `main` that touches `graph/` or the generator, it:

1. Installs RepoGraph from git
2. Runs `python -m private_manifest.export_boundary_artifact --graph-root graph --out boundary/boundary_disclosure_artifact.json --source-graph-id PrivateManifest --source-ref-or-commit "$GITHUB_SHA"`
3. Commits the regenerated artifact back to `main` if it changed

Required workflow permission: `contents: write`.

Run the generator locally once before pushing to seed the initial artifact —
otherwise downstream CI 404s on the first run.

### 3. Generate a fine-grained PAT

In GitHub settings → Developer settings → Personal access tokens → Fine-grained
tokens, create a token with:

- **Resource owner**: the account/org that owns your PrivateManifest
- **Repository access**: *Only select repositories* → your PrivateManifest, nothing else
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
| `REPOGRAPH_BOUNDARY_ARTIFACT_FILE` | `https://raw.githubusercontent.com/<owner>/<PrivateManifest-name>/main/boundary/boundary_disclosure_artifact.json` |

If you're on a **GitHub organization**, set these once as *organization
secrets* and scope them to the consuming repos. Single source, free tier
includes this.

If you're on a **personal account**, there are no org-level secrets. Use
`gh secret set` in a loop to set both secrets in each repo:

```bash
REPOS=(RepoA RepoB RepoC)  # every repo that runs custodian-audit
BOUNDARY_URL="https://raw.githubusercontent.com/<owner>/<PrivateManifest-name>/main/boundary/boundary_disclosure_artifact.json"

printf '%s' 'YOUR_NEW_PAT_HERE' > /tmp/pat
for repo in "${REPOS[@]}"; do
  gh secret set PRIVATEMANIFEST_READ_TOKEN --repo "<owner>/$repo" < /tmp/pat
  gh secret set REPOGRAPH_BOUNDARY_ARTIFACT_FILE --repo "<owner>/$repo" --body "$BOUNDARY_URL"
done
shred -u /tmp/pat
```

When you rotate the PAT (annual or after a leak), run the same loop with the
new token.

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
your PrivateManifest's `main` branch via the raw GitHub URL. Whenever you
update `graph/`, the `publish-boundary` workflow regenerates and commits the
artifact within seconds; the next consumer CI run immediately sees the new
forbidden names. No drift window, no per-repo rotation.

## Multi-tenant note

The boundary artifact contains the **union** of all private names in your
PrivateManifest. If you host private overlays for multiple unrelated tenants
in the same PrivateManifest repo, every consumer sees every tenant's
forbidden names. If that's a concern, run **one PrivateManifest per tenant**
and configure each consuming repo with the appropriate URL.

## Threat model summary

| Threat | Mitigation |
|---|---|
| PAT leaks via compromised CI workflow | PAT is read-only, scoped to one private repo; rotate annually |
| Boundary artifact JSON appears in public CI logs | Materialize step writes to `$RUNNER_TEMP` and only prints provenance line; secrets are masked in GitHub Actions logs |
| Private names leak via PR diff in a public consumer repo | That's exactly what the audit gate catches — `B1` detector scans for any `forbidden_names` in tracked files |
| PrivateManifest unavailable at fetch time | Audit fails closed (CI red); old artifact remains readable from the last commit, so transient outages don't break things |
| Old PAT remains valid after rotation | Fine-grained PATs are independent; revoke the old one explicitly in GitHub settings |

## Reference implementation

The ProtocolWarden ecosystem is the reference implementation. The relevant
repos are public except where noted:

- `ProtocolWarden/PlatformManifest` — public base
- `ProtocolWarden/PrivateManifest` — private overlay (private repo)
- `ProtocolWarden/RepoGraph` — schema + generator library
- `ProtocolWarden/Custodian` — boundary artifact consumer (B1/B2 detectors)

See `docs/architecture/public_private_projection.md` for the projection
semantics and `docs/architecture/visibility_boundary.md` for how visibility
is enforced across the ecosystem.
