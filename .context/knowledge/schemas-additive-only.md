---
topic: schemas
paths: ["src/platform_manifest/schemas/*.json"]
created: 2026-06-02
campaign_id: c-2026-06-02-9f3a
consequence:
  acted_on_commit: null
  tests_green: unknown
tier: cold
pinned: false
last_injected: null
---
## Finding
Schema changes must be additive within a major version; removing or renaming a field is a breaking change that needs a version bump.
## Detail
Consumers pin to a major version and read fields by name. Removing a field, or
narrowing its type, breaks downstream readers silently. Additive changes (new
optional fields) are safe. A removal/rename requires a coordinated major bump
across the manifest and its consumers.
