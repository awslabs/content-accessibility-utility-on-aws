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

## AI quality tier (Phases 7–11) — IMPLEMENTED

Lives in `tests/ai_quality/`. Run with `RUN_AWS_TESTS=1 pytest -m aws`.

- **Phase 7 — Harness & gating (done).** `@pytest.mark.aws` / `@pytest.mark.llm_judge`,
  enforced by a `pytest_collection_modifyitems` skip in `tests/ai_quality/conftest.py`
  (a conftest `pytestmark` does NOT propagate, so the gate is at collection time):
  skips unless `RUN_AWS_TESTS=1` AND credentials resolve. Real `BedrockClient` (Nova 2
  Lite generator) + a separate **stronger judge** fixture (`us.anthropic.claude-sonnet-4-6`),
  adaptive retries.
- **Phase 8 — LLM-as-a-judge (done).** `tests/ai_quality/judge.py`: `judge(output, criteria,
  context) -> Verdict` using Converse forced tool use for reliable structured scoring;
  `temperature=0`; N=3 votes aggregated by mean score ≥ threshold; `Verdict.explain()`
  surfaces every vote's rationale in the assertion message.
- **Phase 9 — Per-surface quality suites (done).** Real generation + judge for: alt text
  (committed image fixtures in `tests/fixtures/images/`), document title, heading, form
  label, link text, and table remediation (hard structural assertion + semantic judge).
- **Phase 10 — Quality baseline (deferred).** Persisting judge scores over time / model-swap
  comparison — not yet built; the harness supports it.
- **Phase 11 — Scheduled CI (done).** `.github/workflows/ai-quality.yml`, `workflow_dispatch`
  + nightly only, AWS creds via OIDC — never on every PR.

### Finding surfaced by this tier

The table-remediation semantic judge (`test_table_scope_semantic_correctness`) is a
documented `xfail`: the current `table_remediation.py` gives the top-left corner header
(`Region`) `scope="row"` instead of `scope="col"` and emits scrambled `headers=` references.
Structural validity (every `<th>` has a valid scope) still passes. Flip the `xfail` to a hard
assertion once the table logic is fixed.

### AI-tier design decisions

1. Judge with a stronger model than the generator (no self-grading).
2. Handle non-determinism: `temperature=0`, N-call majority, pass thresholds.
3. Never accidental: `-m "not aws"` default, env-gated, clear skips.
4. Tables get objective structural checks in addition to the semantic judge.
5. Alt text is the one surface needing committed binary image fixtures.

## Deferred (documented, not silently skipped)

`pdf2html`/BDA, `batch/*`, live S3 upload — need real AWS or heavy mocking; lower ROI.
Tracked here as not-yet-covered rather than assumed.
