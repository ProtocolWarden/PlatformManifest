<!-- Leaf doc: visibility boundary conventions. -->

## Inject

- **Platform manifest is public-only.** `enforce_platform_public_only` rejects
  any private node in the platform manifest. Private repos belong in
  the private-manifest repo, never in `platform_manifest.yaml`.
- **Info-flow rule:** a manifest may host state involving any repo at or below
  its visibility scope. Public (PlatformManifest) cannot host private state;
  private (the private-manifest repo) may host public state.
- **No private names in public files.** Custodian B1 fails any tracked public
  file mentioning a private repo name — including comments. Use generic phrasing
  ("private project consumers"), never the real name.
- **Edges respect the boundary.** A `PlatformManifest -> <private>` edge is a
  leak; cross-boundary edges live in the private-manifest repo.

## Reference

`docs/architecture/visibility_boundary.md` and `vocabulary_audit.md` cover the
full boundary model and the projection consequences; [[projection]] covers how
private→public redaction is applied.
