---
# §2.2b campaign formalization (context-injection-spec.md). This front-matter is
# the consolidation BOUNDARY: minting a new campaign_id (or flipping status to
# 'done') is the detectable successor to today's overwrite-in-place and is what
# gates the Phase 5 consolidation trigger (parsed by .context/.engine/campaign.py).
# Optional and additive — a task.md without this block still parses as an
# 'active' campaign with campaign_id=None.
campaign_id: null          # e.g. c-2026-06-03-XXXX — mint at campaign start
status: active             # active | done
started: null              # YYYY-MM-DD the campaign started
---

# Task

_The current live assignment. One objective at a time._
_Replace contents when the objective changes. Do not accumulate history here — that belongs in log.md._

## Objective

[One or two sentences. What are you building or fixing right now?]

## Context

[Background that makes the objective clearer — constraints, dependencies, recent decisions.]

## Definition of Done

[What does success look like? How will you know this is complete?]
