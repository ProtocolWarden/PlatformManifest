## Summary

<!-- One or two sentences describing what this PR does and why. -->

## Changes

<!-- Bullet list of what changed. -->

-

## Manifest Map Checklist

- [ ] If `data/repo_graph.yaml` changed, the rationale is in the description
- [ ] No new `RepoEdgeType` value without a real consumer query that needs it
- [ ] Legacy aliases preserved (canonical→legacy is one-way; never break existing aliases)
- [ ] Tests cover the new node / edge / loader behavior

## Testing

- [ ] Tests pass: `.venv/bin/python -m pytest`
- [ ] CLI smoke: `platform-manifest list` runs cleanly

## Related Issues

<!-- Closes #N or References #N -->

## Notes for Reviewer

<!-- Anything non-obvious: alias retirements, breaking edge changes, follow-up items. -->
