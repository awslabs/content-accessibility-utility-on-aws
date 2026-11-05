---
title: Accessibility Remediation
layout: default
parent: Reference
nav_order: 2
description: "How the AI-powered remediation works, per-issue strategies, and table handling."
---

<!--
 Copyright 2025 Amazon.com, Inc. or its affiliates.
 SPDX-License-Identifier: Apache-2.0
-->

# Accessibility Remediation

This document explains the accessibility remediation capabilities of the PDF to HTML conversion library, which uses Bedrock models to automatically fix common accessibility issues in generated HTML.

## Overview

The accessibility remediation functionality:

1. Uses the accessibility audit results to identify WCAG 2.1 and 2.2 compliance issues
2. Creates specialized prompts for each issue type (alt text, page titles, ARIA attributes, etc.)
3. Sequentially processes issues through Bedrock models to generate fixes
4. Applies the fixes to the HTML directly
5. Produces a detailed report of successful and failed remediations

## Using the Remediation Functionality

### From the Command Line

You can remediate accessibility issues in two ways:

1. **As part of PDF conversion** (the `process` command remediates by default;
   pass `--skip-remediation` to opt out):
   ```bash
   content-accessibility-utility-on-aws process --input path/to/input.pdf --output output/
   ```

2. **For an existing HTML file with an audit report**:
   ```bash
   content-accessibility-utility-on-aws remediate --input path/to/existing.html --output remediated.html
   ```

#### Available CLI Options

```
Accessibility remediation options:
  --auto-fix           Automatically fix issues where possible
  --max-issues MAX_ISSUES
                      Maximum number of issues to remediate
  --model-id MODEL_ID  Bedrock model ID to use for remediation
  --severity-threshold {critical,major,minor}
                      Minimum severity level to remediate. Default: minor
  --no-ai              Apply only deterministic fixes; make no Bedrock calls
```

To restrict remediation to specific issue types, use the Python API with
`options={"issue_types": ["missing-alt-text", "empty-alt-text"]}` (there is no
`--issue-types` CLI flag on the `remediate` command).

### From Python Code

```python
from content_accessibility_utility_on_aws.api import remediate_html_accessibility

# After performing an accessibility audit that generates an audit report:
remediation_result = remediate_html_accessibility(
    html_path='path/to/file.html',
    audit_report=audit_report,  # Dictionary from accessibility auditor
    image_dir='path/to/images_folder',  # For image-related issues
    output_path='path/to/output.html',  # Where to save remediated HTML
    options={
        'model_id': 'us.anthropic.claude-sonnet-5',
        'max_issues': 10,  # Limit number of issues to process
        'issue_types': ['missing-alt-text', 'empty-alt-text'],  # Only process specific issues
        'severity_threshold': 'major'  # Only 'major' and 'critical' issues
    }
)

print(f"Remediated {remediation_result['issues_remediated']} issues")
```

## Issue Types and Templates

The remediation process uses specialized templates for common accessibility issues. Currently supported issue types include:

| Issue Type | Description | WCAG Criterion |
|------------|-------------|----------------|
| `missing-alt-text` | Images missing alternative text | 1.1.1 |
| `empty-alt-text` | Non-decorative images with empty alt text | 1.1.1 |
| `missing-title` | Document missing a title element | 2.4.2 |
| `skipped-heading-level` | Heading levels that skip (e.g., h1 to h3) | 1.3.1 |
| `empty-heading` | Headings with no content | 1.3.1 |
| `table-missing-headers` | Tables without headers | 1.3.1 |
| `table-missing-scope` | Table headers missing scope attribute | 1.3.1 |
| `target-size-too-small` | Interactive targets smaller than 24×24 CSS px (WCAG 2.2) | 2.5.8 |
| `duplicate-link-text-different-url` | Same link text pointing to different URLs | 2.4.9 |
| Various ARIA issues | Improper ARIA attribute usage | 4.1.1, 4.1.2 |
| Various form issues | Form fields missing labels or accessible names | 1.3.1, 3.3.2 |

The system can process additional issue types using a generic remediation template, but specialized templates provide better results.

### Browser-backed (rendered) issue types

These issue types are produced only by the optional **rendered audit**, which
renders the page in a real headless browser (see the
[Rendered & Agent Guide](rendered_agent_guide.md)); static HTML analysis cannot
detect them:

| Issue Type | Description | WCAG Criterion |
|------------|-------------|----------------|
| `focus-not-visible` | No visible focus indicator on an interactive element | 2.4.7 |
| `computed-contrast-insufficient` | Text/background contrast below threshold (computed from the full cascade, not just inline style) | 1.4.3 / 1.4.11 |
| `missing-accessible-name` | Custom widget / control with no accessible name (model-authored `aria-label`) | 4.1.2 |
| `missing-aria-state` | ARIA role missing its required state (e.g. `aria-checked`) | 4.1.2 |
| `invalid-aria-structure` | ARIA role missing its required parent (e.g. `tab` without `tablist`) | 4.1.2 |
| `focus-order-broken` | Positive `tabindex` distorts keyboard focus order | 2.4.3 |
| `duplicate-id` | Colliding element ids break `label[for]`/aria references | 4.1.1 |

When the accessibility **agent** is used, each such fix is applied, the page is
re-rendered, and the fix is **verified** by a deterministic re-probe before the
issue is marked resolved — unlike the static remediation path, which applies a
fix without re-checking it. Contrast fixes use `author_css_rule` (a real cascade
rule, since an inline attribute cannot beat a stylesheet); the agent can also
call `set_page_state` to reach runtime-only issues (e.g. a modal hidden until
opened) before probing.

## Processing Order and Image Handling

Issues are processed sequentially, one by one, as required by some Bedrock models that have stateful processing. For image-related issues like missing alt text:

1. The system tries to locate the image file if available
2. If found, the image data is included in the prompt to the model
3. The model analyzes the image content to generate appropriate alternative text

Image `src` paths are kept as written (for example `images/chart.png`), and the
image files are copied to the same relative location next to the output.
Remote (`https://`) and `data:` images are left untouched.

## When a model-backed fix fails (needs review)

Remediation fails closed. If a model-backed fix can't be produced (the model
call errors, the image file is missing, or AI is disabled with `--no-ai`), the
document is **not** changed for that issue. Instead:

- The issue gets `remediation_status: "needs_review"` in the remediation report,
  with the error in `error` / `failure_reason` and a `needs_review_reason` of
  `model_failed` or `no_model`.
- No placeholder or generic text is written. The tool no longer adds
  "Image description unavailable", "Image related to this content", "View
  details", "More about …" or "Link to #fragment".
- The result counts these issues in `issues_needs_review`, and counts the subset
  caused by a failed model call in `model_failures`. The CLI exits with code `2`
  when `model_failures` is non-zero.

Before the first model call, Bedrock access is checked once with a minimal
Converse request (credentials, region, and access to the model). If the check
fails, nothing is written: the CLI exits `1` and the API raises
`BedrockUnavailableError`, with a message saying what to fix.

With `--no-ai` (API: `disable_ai=True`), deterministic fixes still run:
language, page title (from existing headings or metadata), landmarks, a single skip link, table
structure, form grouping, duplicate IDs, focus styles, target size, and link
text derived from an external URL's domain. Everything that needs authored
text is listed for review.

> **Behaviour change (unreleased):** earlier versions exited `0` and wrote
> placeholder alt text when Bedrock was unreachable. Scripts that relied on
> exit code `0` should treat `2` as "finished, review needed".

## Example Workflow

A complete remediation workflow typically includes:

1. Converting a PDF to HTML (`convert_pdf_to_html`)
2. Auditing for accessibility issues (`audit_html_accessibility`)
3. Remediating the identified issues (`remediate_html_accessibility`)

See the tests under `tests/remediate/` (e.g.
`tests/remediate/test_model_backed_remediation.py`) for complete examples.

## Advanced Usage

### Custom Models

You can specify different Bedrock model IDs for remediation:

```bash
content-accessibility-utility-on-aws remediate --input document.html --output remediated.html --model-id us.anthropic.claude-sonnet-5
```

### Filtered Remediation

Process only specific issue types via the Python API's `options` dict:

```python
remediate_html_accessibility(
    html_path="document.html",
    audit_report=audit_report,
    output_path="remediated.html",
    options={"issue_types": ["missing-alt-text", "empty-alt-text"]},
)
```

### Severity-Based Remediation

Focus on the most important issues:

```bash
content-accessibility-utility-on-aws remediate --input document.html --output remediated.html --severity-threshold critical
```

## Limitations

1. Some complex issues may not be successfully remediated
2. Image-based alt text generation requires the image files to be accessible
3. Context-dependent issues may have limited remediation success
4. The sequential processing can be slower for documents with many issues
