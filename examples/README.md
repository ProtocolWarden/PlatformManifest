# Example manifests

Two worked examples covering the two valid second-layer manifest kinds.

## `single_project/`

One repo authoring its own `ProjectManifest`. This is the common shape for a
single-repo project.

```bash
platform-manifest validate examples/single_project/project_manifest.yaml --expected project
```

## `work_scope/`

A multi-repo work scope using `manifest_kind: work_scope` (PM v0.9.0+).
`MediaProductCore/` and `MediaProductAssets/` are two ordinary projects
with their own `ProjectManifest`s. `MediaProductSuite/` is the dedicated
shell repo that holds the `WorkScopeManifest` composing them.

```bash
# Validate each constituent project on its own
platform-manifest validate examples/work_scope/MediaProductCore/topology/project_manifest.yaml   --expected project
platform-manifest validate examples/work_scope/MediaProductAssets/topology/project_manifest.yaml --expected project

# Validate the work scope (composes both projects)
platform-manifest validate examples/work_scope/MediaProductSuite/topology/work_scope_manifest.yaml --expected work_scope

# Inspect the merged graph
platform-manifest effective \
  --work-scope examples/work_scope/MediaProductSuite/topology/work_scope_manifest.yaml
```

## Migration: legacy project-shell → work-scope

If you have a manifest authored under PM v0.8.x using `manifest_kind: project`
with `includes:`:

```diff
- manifest_kind: project
+ manifest_kind: work_scope
  manifest_version: "1.0.0"
```

The `includes:` shape is unchanged. PM v0.9.x loaded the legacy form with
a `DeprecationWarning`; PM v1.0.0+ rejects it (schema-level + loader-level).
