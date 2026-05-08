---
name: Feature Request
about: Suggest an improvement or new capability
labels: enhancement
assignees: ''
---

## Summary

A one-sentence description of the feature.

## Problem It Solves

What is currently difficult or impossible that this would fix?

## Proposed Solution

How you imagine it working. Include CLI or YAML examples if relevant.

## Map Scope Check

PlatformManifest is the canonical repo map — describing repos and their relationships, nothing more. Confirm this change stays within that boundary:

- [ ] No execution, dispatch, or routing logic introduced
- [ ] No per-deployment configuration added (those belong in consumer repos)
- [ ] If proposing a new `RepoEdgeType`, name a real consumer query that needs it

## Alternatives Considered

Other approaches and why you ruled them out.

## Additional Context

Related issues, downstream consumers affected, or prior discussion.
