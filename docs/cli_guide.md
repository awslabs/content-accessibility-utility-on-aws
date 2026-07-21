---
title: CLI Guide
layout: default
parent: Get Started
nav_order: 1
description: "Comprehensive reference for the content-accessibility-utility-on-aws command-line interface."
---

<!--
 Copyright 2025 Amazon.com, Inc. or its affiliates.
 SPDX-License-Identifier: Apache-2.0
-->

# CLI Guide

The `content-accessibility-utility-on-aws` command-line interface is the fastest
way to convert, audit, remediate, and translate documents — no code required.
This guide covers installation, every subcommand and its options, configuration
files, and common recipes.

<details markdown="block">
<summary><strong>On this page</strong></summary>

- [5-minute quickstart](#5-minute-quickstart)
- [Installation](#installation)
- [Prerequisites](#prerequisites)
- [Command overview](#command-overview)
- [Common options](#common-options)
- [`convert` — PDF to HTML](#convert--pdf-to-html)
- [`audit` — check accessibility](#audit--check-accessibility)
- [`remediate` — fix issues](#remediate--fix-issues)
- [`translate` — multilingual output (i18n)](#translate--multilingual-output-i18n)
- [`process` — the full pipeline](#process--the-full-pipeline)
- [`init-pipeline` / `deploy-pipeline`](#init-pipeline--deploy-pipeline)
- [Configuration files](#configuration-files)
- [Output structure](#output-structure)
- [Common recipes](#common-recipes)
- [Troubleshooting](#troubleshooting)

</details>

## 5-minute quickstart

Want a result right now? The **audit** path needs only a `pip install` and an
HTML file — no AWS account, S3 bucket, or BDA setup:

```bash
pip install content-accessibility-utility-on-aws

# Produce a human-readable accessibility report for any HTML file
content-accessibility-utility-on-aws audit -i page.html -o report.html -f html
open report.html            # macOS; use xdg-open on Linux
```

Ready for the full **convert → audit → remediate** workflow on a PDF? That path
uses Amazon Bedrock, so set up AWS first ([Prerequisites](#prerequisites)), then:

```bash
export BDA_S3_BUCKET=my-accessibility-bucket
export BDA_PROJECT_ARN=arn:aws:bedrock:us-west-2:123456789012:project/my-project

content-accessibility-utility-on-aws process -i document.pdf -o output/
```

That's it — the sections below cover every command and option in depth.

## Installation

```bash
# Core install (static audit + remediation, no browser)
pip install content-accessibility-utility-on-aws
```

Optional extras layer on additional capabilities:

```bash
# Browser-backed rendered audit (headless Chromium via Playwright)
pip install "content-accessibility-utility-on-aws[rendered]"
playwright install chromium

# Agent: the render -> fix -> verify loop (implies the rendered layer)
pip install "content-accessibility-utility-on-aws[agent]"
playwright install chromium

# i18n: translate content into target languages + multilingual output
pip install "content-accessibility-utility-on-aws[i18n]"
```

Requires **Python 3.11+**. The core package never imports the browser or agent
stack, so static-only workflows stay lightweight. When `[rendered]`/`[agent]`
are not installed, `--rendered`/`--agent` log a warning and fall back to the
static audit.

## Prerequisites

The PDF conversion path uses Amazon Bedrock Data Automation (BDA), which requires
an S3 bucket and a BDA project. Audit/remediate/translate of existing HTML only
need Bedrock model access.

```bash
# 1. Create an S3 bucket for BDA uploads
aws s3 mb s3://my-accessibility-bucket

# 2. Create a BDA project configured for HTML output (note the projectArn)
aws bedrock-data-automation create-data-automation-project \
    --project-name my-accessibility-project \
    --standard-output-configuration '{"document":{"outputFormat":{"textFormat":{"types":["HTML"]}}}}'

# 3. Configure credentials + region
aws configure

# 4. Point the tool at your bucket + project
export BDA_S3_BUCKET=my-accessibility-bucket
export BDA_PROJECT_ARN=arn:aws:bedrock:us-west-2:123456789012:project/my-accessibility-project
```

You must also request access to the Bedrock model used for remediation (e.g.
Claude) in the Bedrock console. See the [API Guide](api_integration_guide#aws-integration)
for full AWS setup detail.

## Command overview

| Command | Purpose |
|---|---|
| `convert` | Convert a PDF to accessible HTML (via BDA) |
| `audit` | Check HTML for WCAG 2.1 / 2.2 issues; write a report |
| `remediate` | Fix accessibility issues in HTML using Bedrock models |
| `translate` | Translate remediated HTML into other languages (`[i18n]`) |
| `process` | Full workflow: convert → audit → remediate (→ translate) |
| `init-pipeline` | Scaffold the managed cloud pipeline deployment files |
| `deploy-pipeline` | Scaffold **and** deploy the managed pipeline end to end |

Show the version or top-level help at any time:

```bash
content-accessibility-utility-on-aws --version
content-accessibility-utility-on-aws --help
content-accessibility-utility-on-aws <command> --help
```

## Common options

These options apply to the processing commands (`convert`, `audit`, `remediate`,
`translate`, `process`):

| Option | Description |
|---|---|
| `--input`, `-i` | Input file or directory path **(required)** |
| `--output`, `-o` | Output file or directory (defaults to a path derived from the input name) |
| `--config`, `-c` | Path to a YAML/JSON [configuration file](#configuration-files) |
| `--save-config` | Save the effective configuration to a file |
| `--profile` | AWS profile name to use for credentials |
| `--s3-bucket` | Name of an existing S3 bucket to use |
| `--debug` | Enable debug logging |
| `--quiet`, `-q` | Only output reports; suppress other output |

Command-line flags always override values from a `--config` file.

## `convert` — PDF to HTML

```bash
content-accessibility-utility-on-aws convert \
  --input path/to/document.pdf --output output/directory
```

| Option | Description |
|---|---|
| `--single-file` | Generate a single output file |
| `--single-page` | Combine all pages into one HTML document |
| `--multi-page` | Keep pages as separate HTML files |
| `--continuous` | Use continuous scrolling layout |
| `--extract-images` | Extract and include images from the PDF (default: on) |
| `--image-format [png\|jpg\|webp]` | Format for extracted images |
| `--embed-images` | Embed images as data URIs in the HTML |
| `--exclude-images` | Omit images entirely |
| `--s3-bucket` | Existing S3 bucket to use for BDA |
| `--bda-project-arn` | ARN of an existing BDA project |
| `--create-bda-project` | Create a new BDA project if needed |
| `--config` | Path to a configuration file |

## `audit` — check accessibility

```bash
# JSON report
content-accessibility-utility-on-aws audit \
  --input path/to/document.html --output report.json --format json

# HTML report
content-accessibility-utility-on-aws audit \
  --input path/to/document.html --output report.html --format html
```

| Option | Description |
|---|---|
| `--format`, `-f [json\|html\|text]` | Output format for the audit report |
| `--checks` | Comma-separated list of checks to run (default: all) |
| `--severity [minor\|major\|critical]` | Minimum severity to include |
| `--detailed` | Include detailed context in the report (default: on) |
| `--summary-only` | Only include summary information |
| `--rendered` | Also render each page in a headless browser to catch computed-style / interactive issues static analysis misses (needs the `[rendered]` extra + `playwright install chromium`) |
| `--agent` | Use the browser-backed agent for the rendered pass (implies `--rendered`; needs `[agent]`) |
| `--config` | Path to a configuration file |

The `--rendered` pass detects things static HTML analysis cannot see — computed
contrast, focus visibility (WCAG 2.4.7), the accessibility tree — using
[axe-core](https://github.com/dequelabs/axe-core). Rendered findings use the same
issue shape as static ones. See the [Rendered Audit & Agent Guide](rendered_agent_guide).

## `remediate` — fix issues

```bash
content-accessibility-utility-on-aws remediate \
  --input path/to/document.html --output remediated.html
```

| Option | Description |
|---|---|
| `--auto-fix` | Automatically fix issues where possible |
| `--max-issues` | Maximum number of issues to remediate |
| `--model-id` | Bedrock model ID to use for remediation |
| `--severity-threshold [minor\|major\|critical]` | Minimum severity to remediate |
| `--audit-report` | Path to an existing audit-report JSON to remediate against |
| `--single-page` | Combine all pages into one HTML document |
| `--multi-page` | Keep pages as separate HTML files |
| `--generate-report` | Generate a remediation report (default: on) |
| `--report-format [html\|json\|text]` | Format for the remediation report |
| `--config` | Path to a configuration file |

Passing `--audit-report` lets you remediate against a report from a prior run
without re-auditing. See [Accessibility Remediation](accessibility_remediation)
for how each issue type is fixed.

## `translate` — multilingual output (i18n)

Translate the (remediated) HTML into one or more target languages. Requires the
`[i18n]` extra. The translation runs on Amazon Bedrock.

```bash
# One accessible file per language (doc.es.html, doc.fr.html, ...)
content-accessibility-utility-on-aws translate \
  --input remediated.html --output out/ --target-languages es,fr,ja

# A single multilingual document with a language selector that auto-selects the
# visitor's browser language on first load
content-accessibility-utility-on-aws translate \
  --input remediated.html --output multilingual.html \
  --target-languages es,fr,ar --multilingual
```

| Option | Description |
|---|---|
| `--target-languages` (alias `--languages`) | Comma-separated BCP-47 codes, e.g. `es,fr,ja` **(required)** |
| `--source-language` | Source language; auto-detected from the document if omitted |
| `--multilingual` | Emit one combined document with an accessible language selector |
| `--no-language-selector` | Omit the visible selector from multilingual output |
| `--no-browser-language` | Do not auto-select the visitor's browser language |
| `--model-id` | Bedrock model ID to use for translation |
| `--config` | Path to a configuration file |

The translator preserves all markup, translates screen-reader-announced
attributes (`alt`, `title`, `aria-label`), sets `lang`/`dir` per language block
(WCAG 3.1.2 Language of Parts), and skips `<script>`/`<style>`/`<code>` and any
element marked `translate="no"`. The selector and browser detection are
progressive enhancements — with JavaScript disabled the default language stays
visible.

## `process` — the full pipeline

Runs the complete workflow against a PDF: convert → audit → remediate → optionally
translate.

```bash
content-accessibility-utility-on-aws process \
  --input path/to/document.pdf --output output/directory
```

| Option | Description |
|---|---|
| `--skip-audit` | Skip the audit step |
| `--skip-remediation` | Skip the remediation step |
| `--audit-format [json\|html\|text]` | Format for the audit report |
| `--severity [minor\|major\|critical]` | Minimum severity for audit and remediation |
| `--auto-fix` | Automatically fix issues where possible |
| `--rendered` | Include the browser-backed rendered audit |
| `--agent` | Use the browser-backed agent for the rendered pass (implies `--rendered`) |
| `--target-languages es,fr,...` | Also translate the result (needs `[i18n]`); add `--multilingual` for one selectable document. Per-language files land in a `translations/` subdirectory |
| `--config` | Path to a configuration file |

All options from the individual commands are also accepted.

## `init-pipeline` / `deploy-pipeline`

These scaffold and deploy the managed, event-driven cloud pipeline. They are
covered in full in the **[Deployable Pipeline Guide](pipeline_guide)**; a quick
reference:

```bash
# Write the deployment files (SAM template, AgentCore runtime app, trigger Lambda)
content-accessibility-utility-on-aws init-pipeline ./a11y-pipeline

# Scaffold AND deploy end to end, prompting for values
content-accessibility-utility-on-aws deploy-pipeline
```

`deploy-pipeline` accepts `--region`, `--input-bucket`, `--bda-bucket`,
`--bda-project-arn`, `--runtime-name`, `--yes`/`-y` (unattended/CI), `--dry-run`
(preview only), and `--force`. `init-pipeline` accepts `--force`.

## Configuration files

Any command accepts `--config path.yaml` to load settings, with CLI flags taking
precedence. Sections map to the processing stages:

```yaml
pdf:
  extract_images: true
  image_format: png
  single_file: true

audit:
  severity_threshold: minor
  detailed_context: true

remediate:
  max_issues: 100
  model_id: us.anthropic.claude-sonnet-5
  severity_threshold: minor
  report_format: json

aws:
  create_bda_project: false
  bda_project_arn: "arn:aws:bedrock:us-west-2:123456789012:project/my-accessibility-project"
  s3_bucket: my-accessibility-bucket
```

Save the effective config (flags + defaults) back out with `--save-config`:

```bash
content-accessibility-utility-on-aws process \
  -i doc.pdf -o out/ --severity minor --image-format png \
  --save-config my_config.yaml
```

See the [Parameter Reference](parameter_reference) for every parameter and its
CLI/API equivalent.

## Output structure

### `convert`

![convert output layout: an output directory containing an extracted_html folder
(with document.html for --single-file, or page-0.html and further pages
otherwise) and an images folder holding the extracted images such as
image-0.png.]({{ '/assets/img/output-tree-convert.svg' | relative_url }})

### `process`

![process output layout: an output directory containing an html folder (converted
HTML plus extracted images), an audit_report file in json, html, or txt, and the
final remediated HTML file — which is remediated_document.html with
--single-page or a remediated_html/ directory with
--multi-page.]({{ '/assets/img/output-tree-process.svg' | relative_url }})

## Common recipes

**Audit an existing HTML file and open the report:**

```bash
content-accessibility-utility-on-aws audit -i page.html -o report.html -f html
```

**Convert, audit, and remediate a PDF in one shot:**

```bash
content-accessibility-utility-on-aws process -i report.pdf -o out/
```

**Full pipeline with the browser-backed verify loop:**

```bash
content-accessibility-utility-on-aws process -i report.pdf -o out/ --agent
```

**Remediate only critical issues, capped at 50 fixes:**

```bash
content-accessibility-utility-on-aws remediate -i page.html -o fixed.html \
  --severity-threshold critical --max-issues 50
```

**Produce a Spanish + French + Japanese multilingual page:**

```bash
content-accessibility-utility-on-aws translate -i fixed.html -o site.html \
  --target-languages es,fr,ja --multilingual
```

## Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| `ConfigurationError: BDA_S3_BUCKET / BDA_PROJECT_ARN` | The PDF path needs an S3 bucket and BDA project. Export the env vars or pass `--s3-bucket` / `--bda-project-arn`. |
| `--rendered`/`--agent` "falling back to static audit" warning | The `[rendered]`/`[agent]` extra isn't installed, or you didn't run `playwright install chromium`. |
| AccessDenied on Bedrock model | Request model access in the Bedrock console for the `--model-id` you're using. |
| Slow or partial remediation | Large documents have many issues; use `--max-issues` and/or a higher `--severity-threshold`. |

Add `--debug` to any command for verbose logs, or `--quiet` to emit only the
report.

---

**Next:** embed this in your own code with the [API Integration Guide](api_integration_guide),
or automate it at scale with the [Deployable Pipeline Guide](pipeline_guide).
