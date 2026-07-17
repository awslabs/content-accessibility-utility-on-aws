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

- **Post-remediation re-audit + gap report.** After remediation the pipeline
  re-audits the final HTML and publishes `accessibility_audit_before.json`,
  `accessibility_audit.json` (now the post-remediation state), and
  `remediation_gap.json` (before/after issue counts + residual-by-criterion), so
  the report reflects what was actually fixed and the residual gap is
  measurable. Job status carries `issues_before`/`issues_after`/`issues_resolved`.
- **`author_css_rule` agent tool + computed-contrast remediation (WCAG 1.4.3 /
  1.4.11).** The agent can inject a real CSS cascade rule (needed for contrast,
  which an inline attribute cannot fix against a stylesheet), reading computed
  colors via `get_element` and verifying with axe. A deterministic
  `computed-contrast-insufficient` strategy (shared luminance math in
  `utils/color_contrast.py`) covers the no-model path.
- **`set_page_state` agent tool (runtime state).** Runs a JS snippet after
  render (e.g. `openModal()`) so runtime-only issues — a modal hidden until
  opened, a live region — become observable and fixable; all later probes/verify
  observe that state. Markup/`document.write` injection is refused.
- **Duplicate-id remediation (WCAG 4.1.1).** A deterministic document-wide pass
  makes colliding `id`s unique and repairs adjacent `label[for]` associations
  (a shared id otherwise resolves only to the first match, mis-labelling
  controls). Mapped from axe `duplicate-id-active`/`-aria`.
- **Focus-order remediation (WCAG 2.4.3).** A tab-order probe reports elements
  with positive `tabindex` (which distort the keyboard sequence); the fix
  neutralizes them to `tabindex="0"` and verify re-walks the order.
- **Name/Role/Value verifier (WCAG 4.1.2).** `verify(selector, "4.1.2")` re-runs
  axe's name/role/state rules scoped to the node, so accessible-name, aria-state,
  and aria-structure fixes can be formally verified and committed through the
  verify-gated loop (previously these had no verifier, so real fixes could not
  be marked resolved).
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


### Security

- **Path-traversal fix in converted-bundle materialization.** A `manifest.json`
  uploaded under the `html/` input prefix is routed to the audit pipeline
  without a provenance check, and its S3 key values flowed into a local write
  target (`os.path.join(work_dir, rel)` → `download_file`) with no confinement —
  so a key containing `..` (S3 keys are opaque and may hold `..`) could write
  the object's bytes outside the temp work dir. `_materialize_bundle` now
  resolves every manifest key through `_bundle_dest`, which confines the
  destination to `work_dir` (realpath prefix check) and rejects traversal,
  matching the existing zip-slip and asset-inlining guards.

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
