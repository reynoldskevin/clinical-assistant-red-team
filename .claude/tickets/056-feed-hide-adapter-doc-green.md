---
id: 056
title: Feed — hide adapter calls, colour documentation green
status: ready-for-merge
depends_on: []
branch: ticket/056-feed-hide-adapter-doc-green
base_branch: main
test_command: ".venv/bin/pytest tests/test_feed_hide_adapter.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 0
---

## Description
The Live agent activity feed lists adapter (target_call) rows that carry no useful
signal, and colours the Documentation agent grey. Hide the adapter rows, and since
adapter previously owned the green accent, give that green to the Documentation
agent (it is a real agent, unlike the deterministic regression substrate which
stays grey).

## Acceptance criteria
- [ ] `renderFeed` filters out activity whose `agent` is `"adapter"` so adapter rows
      never render in the feed.
- [ ] The `.agentchip.doc` (documentation) chip is coloured with the green accent
      (`var(--good)`), no longer grey.
- [ ] The adapter chip is removed from the feed legend/key (adapter is hidden, so it
      should not appear in the key). Documentation stays in the key (now green).
- [ ] Regression (`.agentchip.reg`) stays grey; no other agent colour changes.
- [ ] No other feed behaviour changes; full suite stays green.

## Test plan (orchestrator authors these)
- unit (`tests/test_feed_hide_adapter.py`), asserting on `render_html`:
  - `renderFeed` contains a filter dropping `ev.agent === "adapter"`.
  - the `.agentchip.doc` CSS rule uses `var(--good)`.
  - the legend no longer contains the adapter chip span, but still contains the
    documentation chip span.
