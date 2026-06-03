<!-- Leaf doc: public/private projection conventions. -->

## Inject

- **Validate before emitting.** The safe public-projection command MUST validate
  the projected output before producing it. Unsafe/raw generation is split onto
  an explicit dev-only command — never make the safe path skip validation.
- **Redaction is not optional and runs first.** Public names come from
  RepoGraph's `public_name` redaction; redact before any validation or emission,
  or private fields leak into the projected schema.
- **Projection modules are re-exporters.** `projection/` re-exports from RepoGraph
  via `import_repograph(...)`; do not fork the redaction/validation semantics
  locally — extend them in RepoGraph and re-export.
- **Private is a superset of public.** A private manifest may describe public
  repos; a public projection must drop everything not cleared for public.

## Reference

See `docs/architecture/public_private_projection.md` for the full projection
semantics, redaction behaviour, and the projection test plan; see
[[visibility]] for the boundary rules that govern what may be projected.
