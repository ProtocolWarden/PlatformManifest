<!-- Leaf doc: JSON schema conventions. -->

## Inject

- **`additionalProperties: false` everywhere.** Every schema rejects unknown
  fields. Adding a field to a manifest/model WITHOUT declaring it in the schema
  `$def` is the single most common break here — bundled validation fails with no
  obvious cause. Update the schema in the SAME change as the field.
- **Mirror public + private.** A field added to `platform_manifest.schema.json`
  usually needs the same `$def` in `private_manifest.schema.json` (private is a
  superset). Check both.
- **New optional fields are still declared.** "Optional" means
  `not required`, not "undeclared" — undeclared still fails `additionalProperties`.
- **Re-exported projection fields count.** `to_public_manifest_dict()` emits
  `schema_kind` / `schema_version` / `projection_profile` at root — schema must
  permit them.

## Reference

History: see `.console/log.md` entries on bundled-validation fixes
(2026-05-13, 2026-05-22) for the recurring undeclared-field failure mode.
