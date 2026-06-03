<!-- Leaf doc: loader.py conventions. Only ## Inject is auto-injected. -->

## Inject

- **Fail-closed on visibility.** When `visibility_scope` is absent, derive
  `public` ONLY if every `repos[*].visibility` is public; otherwise **raise**.
  Never silently default a mixed-scope manifest to public.
- **Fail loud, not soft.** Config problems raise `RepoGraphConfigError` — do not
  swallow, do not return a partial graph. A half-loaded manifest is a security
  boundary hazard, not a convenience.
- **Anchor at packaged resources, not CWD.** Default manifest is read via
  `importlib.resources` from the package data, not by walking the filesystem.
  Do not add sibling-directory scanning or globbing (there are explicit
  no-implicit-discovery tests guarding this).
- **The loader does not compose.** Multi-manifest composition lives in
  `composition.py`; keep `loader.py` to parsing + validation of one manifest.

## Reference

Full loader behaviour, the `default_config_path()` resolution, and the
parse_* helpers are documented in `docs/architecture/platformmanifest_ontology.md`
and the `tests/test_visibility_scope.py` / no-implicit-discovery suites.
