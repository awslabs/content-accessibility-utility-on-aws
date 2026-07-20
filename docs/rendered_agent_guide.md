<!--
 Copyright 2025 Amazon.com, Inc. or its affiliates.
 SPDX-License-Identifier: Apache-2.0
-->

# Rendered Audit & Accessibility Agent Guide

This guide covers the optional **browser-backed** layer: a rendered audit that
detects issues static HTML analysis cannot see, and an **agent** that closes the
loop by applying a fix, re-rendering, and verifying it. It also covers how to run
that layer in AWS without shipping a browser binary, using the Amazon Bedrock
AgentCore Browser Tool.

## Table of Contents

- [Why a browser layer](#why-a-browser-layer)
- [Installation](#installation)
- [How it works](#how-it-works)
- [The verify-before-commit guarantee](#the-verify-before-commit-guarantee)
- [Using it](#using-it)
- [Deploying in AWS (AgentCore)](#deploying-in-aws-agentcore)
- [Configuration reference](#configuration-reference)
- [Testing](#testing)
- [Limitations and status](#limitations-and-status)

## Why a browser layer

The core audit and remediation are **static**: they parse HTML with
BeautifulSoup and read inline CSS. That is fast and dependency-light, but it
structurally cannot see anything that only exists once a page is rendered:

- **Computed styles** — contrast from stylesheets/classes (not just inline
  `style`), the accessibility tree, actual rendered geometry.
- **Interactive behavior** — whether a control shows a visible focus indicator
  (WCAG 2.4.7), keyboard/focus order, ARIA state.
- **Dynamic content** — anything injected by JavaScript after load.

The rendered layer renders each page in a real headless browser, runs
[axe-core](https://github.com/dequelabs/axe-core) plus a focus-visibility probe,
and emits findings in the **same issue shape** as the static audit — so the
existing report, grouping, and remediation routing work unchanged.

The **agent** goes one step further: today's static remediation is
fire-and-forget (a fix is "done" when a strategy runs). The agent applies a fix,
**re-renders, and re-checks** that the criterion now passes before marking it
resolved.

## Installation

The browser/agent stack is optional; the core package never imports it.

```bash
# Rendered audit only
pip install "content-accessibility-utility-on-aws[rendered]"

# Agent (implies rendered) — adds Strands and the AgentCore SDK
pip install "content-accessibility-utility-on-aws[agent]"

# One-time browser binary download (for the local backend)
playwright install chromium
```

If an extra is not installed, requesting `--rendered`/`--agent` logs a warning
and falls back to the static audit rather than failing.

## How it works

```
render_and_probe ─► (choose a fix) ─► apply_fix ─► verify ─► resolved
      ▲                                              │
      └───────────── not fixed: try again ◄──────────┘
```

The layer is built around one seam, the **`BrowserProbe`** interface, with three
deterministic operations:

- `render_and_probe(html)` — render, run axe-core + the focus probe, return
  findings as canonical issue dicts.
- `get_element(html, selector)` — computed style, box, role, accessible name for
  one element.
- `verify(html, selector, criterion)` — **re-render** and re-measure whether one
  element now satisfies one WCAG criterion. This is the source of truth for
  "did the fix work".

Two implementations satisfy that interface and share all probe logic through a
common base (`_PlaywrightProbeBase`), so behavior is identical across them:

| Implementation | Backend | Use |
|----------------|---------|-----|
| `LocalPlaywrightProbe` | Local headless Chromium via Playwright | Local dev, CI, the Streamlit webapp |
| `AgentCoreBrowserProbe` | Managed Amazon Bedrock AgentCore Browser Tool over CDP | AWS / hosted; **no Chromium in your artifact** |

The **agent** (`agent/agent.py`) is a [Strands](https://strandsagents.com)
`Agent` given a toolbelt plus a goal ("make this page pass its failing checks").
The model decides which fix to apply and in what order; Strands runs the loop.
The tools are:

- `render_and_probe()` — list outstanding issues (axe + focus/tab-order probes).
- `get_element(selector)` — computed style, box, role, accessible name.
- `apply_fix(selector, issue_type)` — apply the mapped remediation strategy.
- `author_css_rule(selector, declarations)` — inject a real CSS cascade rule.
  Needed for fixes an inline attribute cannot express against a stylesheet — most
  importantly contrast (the agent reads computed colors, picks compliant ones,
  applies the rule, then verifies).
- `set_page_state(script)` — run JS after render (e.g. `openModal()`) so
  runtime-only issues (a modal hidden until opened, a live region) become
  observable; all later probes/verify then see that state.
- `verify(selector, criterion)` — the source of truth (below).
- `mark_issue_resolved(selector, criterion)` — gated: rejected unless a passing
  `verify()` is on record.

When AI is disabled, a deterministic fixed-policy loop
(`agent/deterministic_loop.py`) runs the same render → fix → verify cycle without
the model.

## The verify-before-commit guarantee

The single most important property of the agent: **a fix is only marked resolved
when a deterministic re-probe confirms it.** Detection and verification are always
performed by the browser probe, never by the model. This is enforced by a Strands
**steering hook** that cancels any attempt to mark an issue resolved without a
recorded passing `verify()` for that element and criterion. The model proposes
edits; the browser adjudicates.

## Using it

### CLI

```bash
# Static audit + rendered pass
content-accessibility-utility-on-aws audit -i page.html -o report.json --rendered

# Use the agent to fix and verify interactive issues
content-accessibility-utility-on-aws audit -i page.html -o report.json --agent

# Full pipeline with the rendered pass
content-accessibility-utility-on-aws process -i doc.pdf -o out/ --rendered
```

### Python API — rendered audit

Rendered findings are additive and use the same issue shape, so nothing
downstream changes:

```python
from content_accessibility_utility_on_aws.api import audit_html_accessibility

result = audit_html_accessibility(
    html_path="page.html",
    options={"rendered": True},
    output_path="report.json",
)
```

### Python API — the agent loop

```python
from content_accessibility_utility_on_aws.agent.browser_probe import make_browser_probe
from content_accessibility_utility_on_aws.agent.agent import run_agent

with open("page.html") as f:
    html = f.read()

with make_browser_probe() as probe:          # backend chosen by options/env
    result = run_agent(probe, html)

result["html"]      # remediated HTML
result["resolved"]  # issues confirmed fixed by a passing verify()
result["tool_log"]  # the agent's render/apply_fix/verify/commit trace
```

`make_browser_probe(options)` is the factory that keeps deployment a config
choice: it returns a `LocalPlaywrightProbe` by default, or an
`AgentCoreBrowserProbe` when `options["browser_backend"] == "agentcore"` (or the
`A11Y_BROWSER_BACKEND=agentcore` environment variable is set). Everything above
the probe — the adapter, the rendered auditor, the agent, its tools and hooks —
is identical regardless of which backend is returned.

## Deploying in AWS (AgentCore)

The recommended hosted shape uses the managed **Amazon Bedrock AgentCore Browser
Tool** so you do not bundle or patch a Chromium binary.

### Why AgentCore

- **No browser in your artifact.** The heaviest, most fragile dependency (a
  ~150 MB browser + system libraries) is offloaded to a managed service, keeping
  Lambda/container images small and avoiding image-size limits.
- **Golden Path fit.** Strands is the framework AgentCore runs, and the agent
  already talks to Bedrock for its model calls, so credentials/region/IAM flow is
  the same as the rest of the tool.
- **Longer sessions.** AgentCore Runtime supports multi-hour sessions (vs.
  Lambda's 15 minutes), which suits batch-remediating many documents.

### Deploy the managed pipeline (from a pip install — no repo checkout)

A complete, event-driven pipeline — **document uploaded to S3 → convert (PDF) →
audit → agent-remediate → accessible result written back to S3** — ships with the
package. Deploy it without cloning the repo.

**One-command interactive deploy (recommended).** `deploy-pipeline` scaffolds the
files and runs the whole multi-step deploy for you — it prompts for region,
bucket, and (for the PDF path) BDA config, runs `agentcore configure` →
`agentcore launch` → `sam deploy` in order, and captures the runtime ARN from the
launch output so you never copy it between steps. Every cloud-mutating step is
confirmed first:

```bash
pip install "content-accessibility-utility-on-aws[agent]"
pip install bedrock-agentcore-starter-toolkit aws-sam-cli

content-accessibility-utility-on-aws deploy-pipeline
#   --dry-run                 preview the exact commands, run nothing
#   --yes                     unattended (CI): skips confirmations AND runs
#                             `sam deploy` non-interactively (no --guided prompts)
#   --region / --input-bucket / --bda-bucket / --bda-project-arn  set values non-interactively
```

It shells out to the `agentcore` and `sam` CLIs (it does not reimplement them),
so those must be installed; if either is missing it tells you and stops. If the
runtime ARN can't be parsed from the launch output it falls back to
`.bedrock_agentcore.yaml` and finally prompts, so a parse miss never blocks you.

**Manual steps** (equivalent, if you'd rather run each yourself):

```bash
# 1. Write the deployment files (SAM template, runtime app, trigger Lambda).
content-accessibility-utility-on-aws init-pipeline ./a11y-pipeline
cd a11y-pipeline

# 2. Deploy the AgentCore Runtime (builds an ARM64 image in the cloud; no Docker).
#    For the PDF path, also pass BDA config as runtime env vars.
agentcore configure --entrypoint agentcore_app.py --name a11y_pipeline \
  --requirements-file requirements.txt --region <region>
agentcore launch --env BDA_S3_BUCKET=<bucket> --env BDA_PROJECT_ARN=<bda-project-arn>
#    -> note the runtime ARN it prints.

# 3. Deploy the S3 + Lambda + DynamoDB stack, wiring in that runtime ARN.
sam deploy --guided --parameter-overrides \
  AgentRuntimeArn=<runtime-arn> InputBucketName=<globally-unique-bucket>
```

Then just upload documents (see [Prefix routing](#prefix-routing) below):

```bash
aws s3 cp report.pdf s3://<bucket>/pdf/report.pdf     # PDF  -> accessible/report/
aws s3 cp page.html  s3://<bucket>/html/page.html     # HTML -> accessible/page/
aws s3 cp site.zip   s3://<bucket>/html/site.zip      # zip  -> accessible/site/
```

`init-pipeline` writes a `README.md` next to the files with the same steps, the
IAM the runtime role needs, and the BDA-project setup. Everything is regenerable
— re-run with `--force` to refresh the files after a package upgrade.

<a id="prefix-routing"></a>
The trigger routes by S3 prefix: `pdf/*.pdf` → convert (writes an HTML bundle
under `html/<name>/` plus a `manifest.json` that auto-triggers audit);
`html/<name>.html`, `html/<name>.zip`, or `html/<name>/manifest.json` → audit +
remediate. A single HTML with **external** images degrades to placeholder alt
text (the image bytes are not available to describe) — upload a **zip** bundling
the HTML with its images/CSS/JS to get full multimodal alt text.

Each run writes these to `accessible/<name>/`:

- `<name>.remediated.html` (plus the page's assets) — the fixed document.
- `accessibility_audit_before.json` — findings before remediation.
- `accessibility_audit.json` — findings **after** remediation (the residual).
- `remediation_gap.json` — `issues_before` / `issues_after` / `issues_resolved`
  and residual-by-criterion, so you can measure exactly what was fixed. The same
  counts are recorded on the DynamoDB job record.

### How the connection works

`AgentCoreBrowserProbe` starts a managed browser session
(`BrowserClient.start()`), obtains a signed Chrome DevTools Protocol WebSocket
endpoint (`generate_ws_headers()`), and connects Playwright to it
(`connect_over_cdp`). It stops the session on close, so a session is not left
billing after a run. Everything runs on the probe's dedicated worker thread, so
it is safe under the agent's async event loop.

### Enabling it

Either set an environment variable:

```bash
export A11Y_BROWSER_BACKEND=agentcore
export AWS_REGION=us-west-2
```

or pass options (CLI `--config` file / API `options` dict):

```python
options = {
    "rendered": True,
    "browser_backend": "agentcore",
    "agentcore_region": "us-west-2",
    # "agentcore_browser_id": "aws.browser.v1",  # defaults to the AWS-managed browser
}
```

### Requirements

- The `[agent]` extra (includes the `bedrock-agentcore` SDK).
- AWS credentials with permission to use the AgentCore Browser Tool, plus the
  Bedrock permissions the tool already needs for model/BDA calls.
- An AWS region (from `agentcore_region`, `AWS_REGION`, or `AWS_DEFAULT_REGION`).

### Where to run it

- **Managed pipeline (recommended):** the `init-pipeline` scaffold above deploys
  the agent loop on AgentCore Runtime driving the managed AgentCore browser,
  fronted by an S3-triggered Lambda and DynamoDB job tracking. Nothing to
  check out.
- **Embedded / library use:** call `run_agent(make_browser_probe(...), html)`
  from your own service; set `browser_backend=agentcore` so no Chromium ships in
  your artifact.
- **Fallback:** a Lambda/ECS container image with a bundled headless-chromium
  layer and the `local` backend. Heavier cold starts and you own patching.

## Configuration reference

| Option (dict / config) | CLI flag | Env | Default | Meaning |
|------------------------|----------|-----|---------|---------|
| `rendered` | `--rendered` | — | off | Run the rendered audit in addition to the static audit |
| `agent` | `--agent` | — | off | Use the Strands agent for the rendered pass (implies `rendered`) |
| `browser_backend` | — | `A11Y_BROWSER_BACKEND` | `local` | `local` (Playwright Chromium) or `agentcore` (managed browser) |
| `agentcore_region` | — | `AWS_REGION` / `AWS_DEFAULT_REGION` | env | AWS region for the AgentCore browser |
| `agentcore_browser_id` | — | — | `aws.browser.v1` | AgentCore browser identifier |

## Testing

Tests are tiered so the default suite needs no browser or AWS:

```bash
pytest                      # default: browser-free (adapter, dedupe, hooks, CLI, factory)
pytest -m rendered          # browser-backed (needs [rendered] + `playwright install chromium`)
pytest -m "rendered and aws"  # agent end-to-end (needs Bedrock credentials)
```

The `AgentCoreBrowserProbe` connect/teardown sequence is covered by browser-free
tests that fake the AgentCore SDK, including a regression test that a partial
connect failure does not leak a managed session.

## Limitations and status

- **Scope:** the agent remediates a range of interactive/computed criteria
  end-to-end (apply → re-render → **verify**): focus visibility (2.4.7), computed
  contrast (1.4.3 / 1.4.11), name-role-value on custom widgets (4.1.2), and focus
  order / positive tabindex (2.4.3), plus model-authored accessible names, link
  text, and image alt text. Some fixes are applied by the **static path only**
  (no rendered re-verify) — notably duplicate ids (4.1.1) and structural issues
  (headings, tables, landmarks, language, titles); those pages are not sent to
  the agent.
- **Residual (needs human judgment):** issues that require a page-behavior change
  the agent will not make automatically (e.g. the intended DOM reading order, or
  a modal's default open/closed state) are reported but left for a human. The
  agent honestly reports what it verified vs. left unresolved — see the gap
  report below.
- **AgentCore live validation:** the hosted path (`AgentCoreBrowserProbe` on
  AgentCore Runtime driving the managed browser) has been validated end-to-end
  against live provisioned sessions in a staging account. Still validate in your
  own non-production account before relying on it.
- **Determinism:** rendered runs use a fixed viewport, disable animations, wait
  for network idle, and pin the axe-core build so results are reproducible.
