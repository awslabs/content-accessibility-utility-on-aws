<!--
 Copyright 2025 Amazon.com, Inc. or its affiliates.
 SPDX-License-Identifier: Apache-2.0
-->

# Inaccessible interactive dashboard fixture

A **complex, interactive, deliberately-inaccessible** dashboard, built as a
multi-file bundle (HTML + CSS + JS + images) to **trigger the browser-backed
agent**. **Do not fix these files** — the failures are the point.

Unlike the flat `inaccessible/` fixture (structural issues the static path
handles) and the BDA-converted PDF pages, this one's failures land in the
**agent-relevant** WCAG set the pipeline's candidate filter selects on, so the
render → fix → verify agent loop actually engages.

## Files

- `index.html` — the dashboard (topbar, custom tab bar, filter controls, KPI
  cards, image charts, data table, a modal dialog).
- `css/dashboard.css` — where the computed-style failures live (so static
  inline-CSS analysis can't see them).
- `js/dashboard.js` — click-only widget handlers (no keyboard, no ARIA state).
- `images/` — real-content charts + avatar (so multimodal alt has something to
  describe).

## Intended failures

Agent-relevant (route to the agent):

| SC | Failure |
|----|---------|
| 4.1.2 | custom `div`/`span` tabs, toggles, and icon buttons with no accessible name, no required ARIA state (`aria-checked`/`aria-selected`), and no required parent role (`tablist`); an unlabeled `<select>` |
| 1.4.3 | low-contrast title / KPI value / tab / button text defined in the stylesheet |
| 2.4.7 | `outline: none` on controls (focus indicator) |
| 2.5.8 | 14–16px icon-button / modal-close targets |
| 2.1.1 | widgets operable by click only, no keyboard |

Supporting (static + rendered):

| SC | Failure |
|----|---------|
| 1.1.1 | chart images with missing / empty alt; avatar with no alt |
| 3.3.2 | filter inputs with no labels |
| 1.3.1 | data table with no `<th>`/scope; modal with no dialog role |
| 1.4.1 | KPI deltas / region status shown by color alone |

## Use

**Local rendered audit + agent (single page):**
```bash
content-accessibility-utility-on-aws audit -i tests/fixtures/inaccessible_dashboard/index.html \
  -o /tmp/dash.json --rendered   # or --agent to fix + verify
```

**Cloud pipeline (zip bundle — assets travel with the HTML):**
```bash
( cd tests/fixtures/inaccessible_dashboard && zip -r /tmp/dashboard.zip index.html css js images )
aws s3 cp /tmp/dashboard.zip s3://<input-bucket>/html/dashboard.zip
# result -> s3://<input-bucket>/accessible/dashboard/
```

The rendered audit surfaces ~10 agent-relevant 4.1.2 findings (accessible name,
ARIA state, ARIA structure) plus contrast/focus/target-size — enough for the
per-page candidate filter to select the page and the agent to engage.
