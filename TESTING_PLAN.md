<!--
 Copyright 2025 Amazon.com, Inc. or its affiliates.
 SPDX-License-Identifier: Apache-2.0
-->

# Testing Plan

This document tracks the test strategy for the Content Accessibility Utility.

## Principle: test the offline core, mock the AWS boundary

The audit and remediation logic is pure functions over BeautifulSoup and needs
no AWS:

- `AccessibilityAuditor(html_content="...")` → report dict (string in, no files)
- `RemediationManager(soup, options={"disable_ai": True})` → mutates soup, fully offline
- `BedrockClient` only touches boto3 lazily, guarded by `disable_ai`, so it is
  never constructed in offline tests

AWS is isolated to a few surfaces (`remediate/services/bedrock_client.py`,
`pdf2html` BDA, `batch/*`, and `usage_tracker`'s S3 upload). These are mocked or
deferred in the core suite and exercised only in the opt-in AI tier.

## Two tiers

| Tier | Phases | AWS? | Runs in default CI? | Proves |
|------|--------|------|---------------------|--------|
| Core | 0–6 | No | Yes (gate) | Plumbing & logic correct, regressions caught |
| AI quality | 7–11 | Yes | No (opt-in / scheduled) | AI output is actually good |

`pytest` defaults to `-m "not aws"`, so the AI tier never runs (or costs money)
unless explicitly requested.

## Core tier (Phases 0–6)

- **Phase 0 — Infrastructure.** `test` extra in `pyproject.toml`, `[tool.pytest.ini_options]`,
  `tests/` tree, `conftest.py` with `audit(html)` helper, `make_issue(...)` builder,
  a `fake_bedrock_client` stub, and HTML fixtures.
- **Phase 1 — Audit checks (no mocking).** Per check class: known-bad HTML asserts the
  expected issue type + WCAG criterion; known-good asserts compliant/none. Includes
  `TargetSizeCheck` and color-contrast math.
- **Phase 2 — Rule-based remediations (no mocking).** Per strategy: audit-shaped issue +
  soup → DOM fixed AND re-audit reports the issue gone. Explicit cases for the
  fixed bugs: multi-element pages, `!important` override, DOM-mutation resolution.
- **Phase 3 — Model-backed remediations (fake client).** Model path uses output when a
  client is present; falls back to identical rule behavior when client is None.
- **Phase 4 — Shared utilities.** `find_element_from_issue`, `_normalize_issue_type`,
  `css_dimensions`, `text_generation` cleaners, usage tracker accounting.
- **Phase 5 — End-to-end (offline, tmp_path).** Write HTML → `audit_html_accessibility` →
  `remediate_html_accessibility(disable_ai=True)` → output exists, fewer issues.
- **Phase 6 — CI.** `test.yml` runs `pytest --cov` (`-m "not aws"`) on push/PR across
  Python 3.11–3.13, gating before publish.

## AI quality tier (Phases 7–11) — implemented after the core

- **Phase 7 — Harness & gating.** `@pytest.mark.aws` / `@pytest.mark.llm_judge`, env-gated
  (`RUN_AWS_TESTS=1`), real `BedrockClient` + a separate **stronger judge model**
  fixture, retry/backoff, cost logging.
- **Phase 8 — LLM-as-a-judge.** `judge(output, criteria, context) -> {score, pass, rationale}`
  using structured output; criterion-specific WCAG rubrics; judge at `temperature=0`,
  N=3 majority + threshold (not exact match); failures surface the judge rationale.
- **Phase 9 — Per-surface quality suites.** Real generation + judge for the six AI outputs:
  alt text (needs committed test images), document title, heading, form label, link text,
  table remediation (structural validity assertion + semantic judge).
- **Phase 10 — Quality baseline (optional).** Persist judge scores over time; model-swap
  comparison across candidate model IDs.
- **Phase 11 — Optional CI.** Separate `ai-quality.yml`, `workflow_dispatch` / nightly only,
  AWS creds via OIDC — never on every PR.

### AI-tier design decisions

1. Judge with a stronger model than the generator (no self-grading).
2. Handle non-determinism: `temperature=0`, N-call majority, pass thresholds.
3. Never accidental: `-m "not aws"` default, env-gated, clear skips.
4. Tables get objective structural checks in addition to the semantic judge.
5. Alt text is the one surface needing committed binary image fixtures.

## Deferred (documented, not silently skipped)

`pdf2html`/BDA, `batch/*`, live S3 upload — need real AWS or heavy mocking; lower ROI.
Tracked here as not-yet-covered rather than assumed.
