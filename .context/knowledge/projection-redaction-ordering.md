---
topic: projection
paths: ["src/platform_manifest/projection/**"]
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
Redaction must run before validation, or private fields leak into the projected schema.
## Detail
The projection pipeline applies visibility/redaction rules and then validates
the projected document against the public schema. If validation runs first,
private fields are still present and either (a) fail validation spuriously or
(b) pass through into the emitted projection when the schema is permissive.
Order is: load -> redact -> validate -> emit. See the projection rules module
and its visibility helpers.
