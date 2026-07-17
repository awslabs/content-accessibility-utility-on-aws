# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]


### Changed

- Default Bedrock model is now Claude Sonnet 5 (`us.anthropic.claude-sonnet-5`),
  up from Amazon Nova 2 Lite, for higher-quality semantic authoring (accessible
  names, link text, alt text). Override via `--model-id` / `options["model_id"]`;
  Nova 2 Lite remains a valid lower-cost choice for high-volume batch runs.

### Added

- `init-pipeline` CLI command: scaffolds the managed AgentCore deployment (SAM
  template, runtime entrypoint, trigger Lambda, requirements) into a directory,
  so the event-driven S3 → convert → audit → agent-remediate → S3 pipeline can be
  deployed from a `pip install` alone — no repository checkout. The deployment
  assets ship as package data.
- `duplicate-link-text-different-url` remediation (WCAG 2.4.9): model-authored
  disambiguation of same-text/different-URL links, with a rule-based fallback.
- Optional browser-backed **rendered audit** (`--rendered` / `options["rendered"]`)
  that renders each page in a real headless browser (Playwright) and runs
  axe-core plus a focus-visibility probe, detecting computed-style and
  interactive issues static HTML analysis cannot see (e.g. WCAG 2.4.7 focus
  visibility). Rendered findings use the same issue shape as the static audit,
  so reports and remediation routing are unchanged.
- Optional **accessibility agent** (`--agent` / `options["agent"]`) built on
  [Strands](https://strandsagents.com) that drives a render → fix → **verify**
  loop: it applies a remediation, re-renders, and only marks an issue resolved
  when a deterministic re-probe confirms the fix. Enforced by a steering hook so
  the model can never mark an unverified fix as done.
- `focus-not-visible` remediation strategy (WCAG 2.4.7) that injects a scoped
  `:focus-visible` outline.
- New optional dependency extras: `[rendered]` (Playwright) and `[agent]`
  (Playwright + Strands + `bedrock-agentcore`). The core install is unchanged
  and never imports the browser/agent stack. Run `playwright install chromium`
  once after installing an extra.
- `AgentCoreBrowserProbe` and the `make_browser_probe()` factory: run the
  rendered/agent layer against the managed Amazon Bedrock AgentCore Browser Tool
  (no local Chromium) by setting `options["browser_backend"] = "agentcore"` or
  the `A11Y_BROWSER_BACKEND=agentcore` environment variable. See
  `docs/rendered_agent_guide.md`.


### Bug Fixes

- The browser-backed **agent now runs on single-file HTML**, not only on
  multi-page (PDF-converted) bundles. Interactive single-page documents
  (dashboards, widgets) are the agent's core case, and it was previously
  unreachable for them, so computed-style/interactive issues went unremediated.
- **Linked local CSS/JS is inlined before the agent renders** the page. The
  probe renders an HTML string (and the hosted browser is a remote managed
  service), so external `<link>`/`<script>` assets never loaded — hiding
  computed-style issues defined in stylesheets (focus outlines via `outline`,
  class-based contrast) from axe and the focus probe. Inlining makes them
  visible so the agent can actually detect and fix them. Only same-origin
  relative paths inside the document directory are inlined (absolute URLs and
  path traversal are refused; oversized assets are skipped).
- Model-agnostic `temperature` handling: newer Bedrock models (e.g. Claude
  Sonnet 5, Opus 4) reject the `temperature` inference parameter with a
  `ValidationException`, which previously caused every model-backed remediation
  to silently fall back to generic rule-based output. The Converse client now
  omits `temperature` proactively for models known to reject it (decided from
  the model id, so rapid short-lived clients never lose the race by each
  sending it once), with a reactive drop-and-retry as a fallback for unknown
  future models. The Strands agent applies the same rule. Models that require
  it (e.g. Nova) still receive `temperature=0.0`.
- Added missing build dependency
- Resolved audit issue with blended numbered html pages and non-numbered pages.
- Improved table generation with solid borders
- Update version to 0.6.2 in the accessibility package
- Code scanning alert no. 1: Workflow does not contain permissions (#3) ([#3](https://github.com/awslabs/content-accessibility-utility-on-aws/pull/3))



### CI/CD

- Enhance release workflow with tag validation and TestPyPI support
- Restrict publish workflow to tag pushes only (#5) ([#5](https://github.com/awslabs/content-accessibility-utility-on-aws/pull/5))



### Documentation

- Update streamlit documentation to reference the correct python package



### Features

- **ci:** Separate RC and production release workflows
- Update to latest Bedrock models, add test suite, and WCAG 2.2 target-size support (#6) ([#6](https://github.com/awslabs/content-accessibility-utility-on-aws/pull/6))



### Miscellaneous

- Updated files for local dev
- Empty commit to trigger new commit build
- Add misc/ directory and .DS_Store to gitignore



### Refactoring

- Renamed module

<!-- generated by git-cliff -->
