<!--
 Copyright 2025 Amazon.com, Inc. or its affiliates.
 SPDX-License-Identifier: Apache-2.0
-->

# Inaccessible test fixture

A deliberately **complex but inaccessible** page for evaluating the audit +
remediation pipeline end-to-end. **Do not fix these files** — the failures are
the point.

Files:
- `report.html` — a realistic operations dashboard (nav, image charts, data
  table, form, custom widgets, links).
- `app.js`, `images/` — assets referenced by the page (for the zip-bundle path).

## Intended WCAG failures

| SC | Failure in the fixture |
|----|------------------------|
| 3.1.1 | `<html>` has no `lang` |
| 2.4.2 | no `<title>` |
| 1.4.3 | low-contrast text defined in the stylesheet (static analysis misses; rendered audit catches) |
| 2.4.7 | `outline:none` on all controls — no visible focus indicator |
| 1.1.1 | logo/chart images with missing, empty, and generic (`alt="chart"`) alt |
| 1.3.1 | heading jumps h1→h4; data table with no `<th>`/scope/caption; no landmarks |
| 2.4.4 | link text "click here" / "read more" / a bare URL |
| 4.1.2 | `div`/`span` "buttons" and a toggle with no role, name, or state |
| 3.3.2 | form inputs with no associated `<label>`; radio group with no `<fieldset>` |
| 2.5.8 | 12×12 px icon button (below the 24×24 minimum) |
| 1.4.1 | table status shown by color alone |

## How to use

**Local:**
```bash
content-accessibility-utility-on-aws audit -i tests/fixtures/inaccessible/report.html -o /tmp/report.json --rendered
```

**Cloud pipeline (single HTML — skips conversion):**
```bash
aws s3 cp tests/fixtures/inaccessible/report.html \
  s3://<input-bucket>/html/report.html --profile <profile>
# result -> s3://<input-bucket>/accessible/report/
```

**Cloud pipeline (zip of HTML+CSS+JS):** build the bundle and upload it:
```bash
( cd tests/fixtures/inaccessible && zip -r /tmp/report_bundle.zip report.html app.js images )
aws s3 cp /tmp/report_bundle.zip s3://<input-bucket>/html/report_bundle.zip --profile <profile>
# result -> s3://<input-bucket>/accessible/report_bundle/
```
