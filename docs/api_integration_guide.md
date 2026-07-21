---
title: API Integration Guide
layout: default
parent: Get Started
nav_order: 2
description: "Integrate the Content Accessibility library into your own Python applications."
---

<!--
 Copyright 2025 Amazon.com, Inc. or its affiliates.
 SPDX-License-Identifier: Apache-2.0
-->

# Content Accessibility Utility on AWS — API Integration Guide

This guide provides instructions for integrating the Content Accessibility
library into your Python applications.

<details markdown="block">
<summary><strong>On this page</strong></summary>

- [Overview](#overview)
- [Installation](#installation)
- [Core Concepts](#core-concepts)
- [Basic Usage](#basic-usage)
- [Advanced Integration](#advanced-integration)
- [Error Handling](#error-handling)
- [Configuration Management](#configuration-management)
- [AWS Integration](#aws-integration)
- [Batch Processing](#batch-processing)
- [API Reference](#api-reference)

</details>

## Overview

The library provides a programmatic API for:

1. Converting PDF documents to accessible HTML (via AWS Bedrock Data Automation)
2. Auditing HTML content for WCAG 2.1 compliance
3. Remediating accessibility issues automatically (via AWS Bedrock models)
4. Processing documents in batch mode
5. Generating comprehensive accessibility reports

Each step can be used independently or as part of the complete pipeline.

## Installation

### Basic Installation

```bash
pip install "content-accessibility-utility-on-aws"
```

### Optional Extras

```bash
# Streamlit web application
pip install "content-accessibility-utility-on-aws[WebApp]"

# Browser-backed rendered audit (headless Chromium via Playwright)
pip install "content-accessibility-utility-on-aws[rendered]"
playwright install chromium

# Agent layer (rendered + Strands + AgentCore SDK)
pip install "content-accessibility-utility-on-aws[agent]"
playwright install chromium

# Internationalization: translate output into other languages (i18n)
pip install "content-accessibility-utility-on-aws[i18n]"
```

The `[i18n]` extra adds localized language display names (Babel) and
source-language auto-detection (langdetect); both degrade to built-in fallbacks
when absent, so it is a quality upgrade rather than a hard requirement for
translation itself.

### Development Installation

```bash
git clone https://github.com/awslabs/content-accessibility-utility-on-aws.git
cd content-accessibility-utility-on-aws
pip install -e ".[test]"
```

### Requirements

- Python 3.11+
- AWS credentials (for PDF conversion and model-based remediation)
- An S3 bucket (for PDF conversion via BDA)
- Access to AWS Bedrock models (for remediation)

## Core Concepts

### Processing Pipeline

The library follows a three-step pipeline architecture:

1. **Conversion**: PDF → HTML (via Bedrock Data Automation)
2. **Audit**: HTML → Accessibility Report
3. **Remediation**: HTML + Report → Accessible HTML

![API processing pipeline: a PDF document goes through convert_pdf_to_html() to
HTML content, which audit_html_accessibility() turns into an accessibility
report; remediate_html_accessibility() takes the HTML plus that report and
produces both remediated HTML and a remediation report.]({{ '/assets/img/api-pipeline-flow.svg' | relative_url }})

Each step can be used independently or as part of the full pipeline via
`process_pdf_accessibility()`.

## Basic Usage

### Full Processing Pipeline

```python
from content_accessibility_utility_on_aws.api import process_pdf_accessibility

result = process_pdf_accessibility(
    pdf_path="document.pdf",
    output_dir="output/",
    conversion_options={
        "extract_images": True,
        "image_format": "png",
    },
    audit_options={
        "severity_threshold": "minor",
    },
    remediation_options={
        "auto_fix": True,
    },
    perform_audit=True,
    perform_remediation=True,
)

# Access results
html_path = result["conversion_result"]["html_path"]
audit_issues = result["audit_result"]["issues"]
remediation = result["remediation_result"]
```

### Step-by-Step Processing

```python
from content_accessibility_utility_on_aws.api import (
    convert_pdf_to_html,
    audit_html_accessibility,
    remediate_html_accessibility,
    generate_remediation_report,
)

# Step 1: Convert PDF to HTML
conversion_result = convert_pdf_to_html(
    pdf_path="document.pdf",
    output_dir="output/",
    options={"extract_images": True, "image_format": "png"},
)
html_path = conversion_result["html_path"]

# Step 2: Audit HTML for accessibility issues
audit_result = audit_html_accessibility(
    html_path=html_path,
    options={"severity_threshold": "minor"},
    output_path="output/audit_report.json",
)

# Step 3: Remediate accessibility issues
remediation_result = remediate_html_accessibility(
    html_path=html_path,
    audit_report=audit_result,
    options={"auto_fix": True},
    output_path="output/remediated.html",
)

# Step 4: Generate a remediation report
generate_remediation_report(
    remediation_data=remediation_result,
    output_path="output/remediation_report.html",
    report_format="html",
)
```

### Audit-Only (HTML Input)

If you already have HTML content and only need an accessibility audit:

```python
from content_accessibility_utility_on_aws.api import audit_html_accessibility

result = audit_html_accessibility(
    html_path="page.html",
    options={
        "severity_threshold": "major",
        "check_images": True,
        "check_headings": True,
        "check_tables": True,
        "check_color_contrast": True,
    },
    output_path="audit_report.json",
)

print(f"Issues found: {len(result['issues'])}")
for issue in result["issues"]:
    print(f"  [{issue['severity']}] {issue['type']}: {issue.get('message', '')}")
```

### Remediate Without Re-Auditing

If you already have an audit report (e.g., from a prior run):

```python
import json
from content_accessibility_utility_on_aws.api import remediate_html_accessibility

with open("audit_report.json") as f:
    audit_report = json.load(f)

# Filter to only issues that need remediation
filtered_report = {
    "issues": [
        issue for issue in audit_report.get("issues", [])
        if issue.get("remediation_status") == "needs_remediation"
    ],
    "summary": audit_report.get("summary", {}),
}

result = remediate_html_accessibility(
    html_path="page.html",
    audit_report=filtered_report,
    options={"auto_fix": True},
    output_path="remediated_page.html",
)
```

### Translating Output (i18n)

Translate the remediated HTML into one or more target languages with
`translate_html_accessibility()`. It translates the visible content and the
screen-reader-announced attributes (`alt`, `title`, `aria-label`, ...) on Amazon
Bedrock while preserving all markup and accessibility structure. Requires the
[`[i18n]` extra](#optional-extras). Translation is a separate step —
`process_pdf_accessibility()` runs convert → audit → remediate only.

```python
from content_accessibility_utility_on_aws.api import translate_html_accessibility

# One accessible file per language, written into a directory.
result = translate_html_accessibility(
    html_path="remediated.html",
    options={"target_languages": ["es", "fr", "ja"]},
    output_path="out/",
)

# Or a single multilingual document with an accessible language selector that
# auto-selects the visitor's browser language on first load.
result = translate_html_accessibility(
    html_path="remediated.html",
    options={
        "target_languages": ["es", "fr", "ar"],
        "multilingual": True,
    },
    output_path="multilingual.html",
)

result["source_language"]   # detected (or supplied) source language
result["target_languages"]  # languages produced
result["multilingual"]      # whether a combined document was emitted
result["output_files"]      # paths written
```

The `options` dict is merged over the `i18n` configuration section:

| Option | Type | Default | Description |
|---|---|---|---|
| `target_languages` | `list[str]` \| `str` | — | **Required.** BCP-47 codes, e.g. `["es", "fr", "ja"]` |
| `source_language` | `str` | auto-detected | Source language; detected from the document when omitted |
| `multilingual` | `bool` | `False` | Emit one combined document with a language selector instead of one file per language |
| `add_language_selector` | `bool` | `True` | Show the visible selector in multilingual output |
| `use_browser_language` | `bool` | `True` | Auto-select the visitor's browser language on first load |
| `batch_size` | `int` | `20` | Segments per Bedrock call |
| `model_id` | `str` | default model | Bedrock model ID to use for translation |

The translator sets `lang`/`dir` per language block (WCAG 3.1.2 Language of
Parts), and skips `<script>`, `<style>`, `<code>`, and any element marked
`translate="no"`. The selector and browser detection are progressive
enhancements — with JavaScript disabled the default language stays visible.

`translate_html_accessibility()` raises `TranslationError` on missing or invalid
languages or a translation failure, and `FileNotFoundError` if `html_path` does
not exist.

## Advanced Integration

### Multi-Page Document Processing

The library supports both single-page and multi-page modes. When BDA produces
multiple HTML files (one per page), the audit and remediation steps can process
them as a directory:

```python
from content_accessibility_utility_on_aws.api import (
    convert_pdf_to_html,
    audit_html_accessibility,
    remediate_html_accessibility,
)

# Convert to multiple HTML files (one per page)
conversion_result = convert_pdf_to_html(
    pdf_path="large_document.pdf",
    output_dir="output/",
    options={"multiple_documents": True},
)

# Audit the directory of HTML files
audit_result = audit_html_accessibility(
    html_path=conversion_result["html_path"],
    options={"multi_page": True},
    output_path="output/audit_report.json",
)

# Remediate all pages
remediation_result = remediate_html_accessibility(
    html_path=conversion_result["html_path"],
    audit_report=audit_result,
    options={"multi_page": True},
    output_path="output/remediated_html/",
)
```

### Using the Rendered Audit (Browser-Backed)

The rendered layer detects issues that static HTML analysis cannot see — computed
styles, focus visibility, interactive behavior:

```python
from content_accessibility_utility_on_aws.api import audit_html_accessibility

result = audit_html_accessibility(
    html_path="page.html",
    options={
        "rendered": True,        # Run axe-core in a real browser
        "severity_threshold": "minor",
    },
    output_path="rendered_audit.json",
)
```

### Using the Agent Loop

The agent applies fixes, re-renders, and verifies each fix passed before marking
it resolved:

```python
from content_accessibility_utility_on_aws.agent.browser_probe import make_browser_probe
from content_accessibility_utility_on_aws.agent.agent import run_agent

with open("page.html") as f:
    html = f.read()

with make_browser_probe() as probe:
    result = run_agent(probe, html)

result["html"]      # remediated HTML
result["resolved"]  # issues confirmed fixed by a passing verify()
result["tool_log"]  # the agent's render/apply_fix/verify/commit trace
```

To use the managed AgentCore browser backend (no local Chromium needed):

```python
with make_browser_probe(options={"browser_backend": "agentcore"}) as probe:
    result = run_agent(probe, html)
```

### Usage Tracking

The library tracks BDA and Bedrock API usage automatically. Save usage data to a
local file or S3:

```python
from content_accessibility_utility_on_aws.api import (
    process_pdf_accessibility,
    save_usage_data,
)

result = process_pdf_accessibility(
    pdf_path="document.pdf",
    output_dir="output/",
    perform_audit=True,
    perform_remediation=True,
    usage_data_bucket="my-usage-bucket",
    usage_data_bucket_prefix="accessibility-runs/",
)

# Or save usage data manually after processing
save_usage_data(
    output_path="output/usage_data.json",
    usage_data_bucket="my-usage-bucket",
)
```

## Error Handling

The library defines a hierarchy of exceptions:

| Exception | When |
|-----------|------|
| `DocumentAccessibilityError` | Base class for all errors |
| `PDFConversionError` | PDF-to-HTML conversion failures |
| `AccessibilityAuditError` | Audit processing failures |
| `AccessibilityRemediationError` | Remediation failures |
| `TranslationError` | Translation (i18n) failures, e.g. missing or invalid target languages |
| `ConfigurationError` | Invalid configuration or missing settings |

### Example with Error Handling

```python
from content_accessibility_utility_on_aws.api import convert_pdf_to_html
from content_accessibility_utility_on_aws.utils.logging_helper import (
    DocumentAccessibilityError,
    PDFConversionError,
    ConfigurationError,
)

try:
    result = convert_pdf_to_html(
        pdf_path="document.pdf",
        output_dir="output/",
    )
except FileNotFoundError as e:
    print(f"Input file not found: {e}")
except ConfigurationError as e:
    print(f"AWS configuration issue (check BDA_S3_BUCKET / BDA_PROJECT_ARN): {e}")
except PDFConversionError as e:
    print(f"BDA conversion failed: {e}")
except DocumentAccessibilityError as e:
    print(f"Processing error: {e}")
```

## Configuration Management

### Environment Variables

The library reads configuration from environment variables:

| Variable | Description | Used by |
|----------|-------------|---------|
| `BDA_S3_BUCKET` | S3 bucket for BDA file uploads | PDF conversion |
| `BDA_PROJECT_ARN` | BDA project ARN | PDF conversion |
| `AWS_REGION` / `AWS_DEFAULT_REGION` | AWS region for AWS clients | All AWS calls |
| `A11Y_BROWSER_BACKEND` | `local` (default) or `agentcore` | Rendered audit / agent |

Standard AWS credential variables (`AWS_PROFILE`, etc.) are honored by boto3 as
usual. `BDA_S3_BUCKET` / `BDA_PROJECT_ARN` are only needed for the PDF path.

### Configuration Files

Load settings from a YAML or JSON file:

```python
from content_accessibility_utility_on_aws.utils.config import load_config_file, config_manager

# Load from YAML
config_data = load_config_file("accessibility_config.yaml")

# Apply to the config manager by section
for section in ("pdf", "audit", "remediate", "aws"):
    if section in config_data:
        config_manager.set_user_config(config_data[section], section)
```

Example YAML configuration file:

```yaml
pdf:
  extract_images: true
  image_format: png
  multiple_documents: false

audit:
  severity_threshold: minor
  check_images: true
  check_headings: true
  check_tables: true
  check_color_contrast: true

remediate:
  auto_fix: true
  fix_images: true
  fix_headings: true
  fix_tables: true
  severity_threshold: minor

aws:
  s3_bucket: my-accessibility-bucket
  bda_project_arn: "arn:aws:bedrock:us-west-2:123456789012:data-automation-project/my-project"
```

Save configuration from the CLI with `--save-config`:

```bash
content-accessibility-utility-on-aws process \
    -i doc.pdf -o out/ \
    --severity minor --image-format png \
    --save-config my_config.yaml
```

### CLI Configuration File Usage

```bash
content-accessibility-utility-on-aws process \
    -i document.pdf -o output/ \
    --config accessibility_config.yaml
```

## AWS Integration

### Prerequisites

1. **S3 Bucket** — used by BDA for file uploads during PDF conversion:
   ```bash
   aws s3 mb s3://my-accessibility-bucket
   ```

2. **BDA Project** — a Bedrock Data Automation project configured for HTML output:
   ```bash
   aws bedrock-data-automation create-data-automation-project \
       --project-name my-accessibility-project \
       --standard-output-configuration '{"document":{"outputFormat":{"textFormat":{"types":["HTML"]}}}}'
   ```

3. **Bedrock Model Access** — request access to the model used for remediation
   (e.g., Claude) in the AWS Bedrock console.

### Credentials

The library uses the standard boto3 credential chain. You can specify a named
profile:

```python
from content_accessibility_utility_on_aws.api import process_pdf_accessibility

result = process_pdf_accessibility(
    pdf_path="document.pdf",
    output_dir="output/",
    profile="my-aws-profile",
    perform_audit=True,
    perform_remediation=True,
)
```

Or pass S3 bucket and BDA project ARN directly:

```python
from content_accessibility_utility_on_aws.api import convert_pdf_to_html

result = convert_pdf_to_html(
    pdf_path="document.pdf",
    output_dir="output/",
    s3_bucket="my-bucket",
    bda_project_arn="arn:aws:bedrock:us-west-2:123456789012:data-automation-project/my-project",
)
```

To create a new BDA project on the fly:

```python
result = convert_pdf_to_html(
    pdf_path="document.pdf",
    output_dir="output/",
    s3_bucket="my-bucket",
    create_bda_project=True,
)
```

## Batch Processing

The `batch` module provides functions for processing documents at scale in a
decoupled architecture using AWS services.

### Batch PDF Processing

```python
from content_accessibility_utility_on_aws.batch.pdf2html import process_pdf_document

result = process_pdf_document(
    pdf_path="document.pdf",
    s3_bucket="my-bucket",
    bda_project_arn="arn:aws:bedrock:us-west-2:123456789012:data-automation-project/my-project",
    output_dir="output/",
)
```

### Batch HTML Audit

```python
from content_accessibility_utility_on_aws.batch.audit import (
    process_html_document,
    process_html_directory,
)

# Single file
result = process_html_document(
    html_path="page.html",
    output_dir="output/",
)

# Directory of HTML files
result = process_html_directory(
    html_dir="pages/",
    output_dir="output/",
)
```

### Batch Remediation

```python
from content_accessibility_utility_on_aws.batch.remediate import (
    process_html_with_audit,
    process_html_directory_with_combined_audit,
)

# Single file: audit + remediate
result = process_html_with_audit(
    html_path="page.html",
    output_dir="output/",
)

# Directory: audit + remediate all files
result = process_html_directory_with_combined_audit(
    html_dir="pages/",
    output_dir="output/",
)
```

### Managed Pipeline (Event-Driven)

For fully automated processing, deploy the managed pipeline which triggers on S3
uploads. See the [Rendered Agent Guide](rendered_agent_guide.md#deploying-in-aws-agentcore)
for the `deploy-pipeline` command.

## API Reference

### Main API Functions (`content_accessibility_utility_on_aws.api`)

| Function | Description | Returns |
|----------|-------------|---------|
| `process_pdf_accessibility()` | Full pipeline: convert, audit, remediate | Dict with `conversion_result`, `audit_result`, `remediation_result` |
| `convert_pdf_to_html()` | Convert PDF to HTML via BDA | Dict with `html_path`, `html_files`, `image_files` |
| `audit_html_accessibility()` | Audit HTML for WCAG issues | Dict with `issues`, `summary`, `report` |
| `remediate_html_accessibility()` | Fix accessibility issues in HTML | Dict with `issues_processed`, `issues_remediated`, `issues_failed`, `remediated_html_path` |
| `translate_html_accessibility()` | Translate remediated HTML into other languages (requires `[i18n]`) | Dict with `source_language`, `target_languages`, `multilingual`, `output_files` |
| `generate_remediation_report()` | Generate an HTML/JSON/text report | Dict with report data |
| `save_usage_data()` | Save session usage metrics to file or S3 | Path string or None |

### CLI Commands

```bash
# Convert PDF to HTML
content-accessibility-utility-on-aws convert -i doc.pdf -o output/

# Audit HTML
content-accessibility-utility-on-aws audit -i page.html -o report.json

# Audit with rendered browser layer
content-accessibility-utility-on-aws audit -i page.html -o report.json --rendered

# Remediate HTML
content-accessibility-utility-on-aws remediate -i page.html -o remediated.html

# Translate remediated HTML into other languages (requires [i18n])
content-accessibility-utility-on-aws translate -i remediated.html -o out/ --target-languages es,fr,ja

# Full pipeline
content-accessibility-utility-on-aws process -i doc.pdf -o output/

# Full pipeline with agent
content-accessibility-utility-on-aws process -i doc.pdf -o output/ --agent

# Deploy the managed S3-triggered pipeline
content-accessibility-utility-on-aws deploy-pipeline
```

### Exception Hierarchy

![Exception hierarchy: DocumentAccessibilityError is the base class of
PDFConversionError, AccessibilityAuditError, AccessibilityRemediationError,
ConfigurationError, and ResourceError.]({{ '/assets/img/exception-hierarchy.svg' | relative_url }})

### Key Options

#### Conversion Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `extract_images` | bool | True | Extract and embed images |
| `image_format` | str | "png" | Image format: png, jpg, webp |
| `multiple_documents` | bool | False | One HTML file per page |
| `single_file` | bool | False | Single output file |
| `embed_images` | bool | False | Embed images as data URIs |
| `exclude_images` | bool | False | Omit images entirely |
| `cleanup_bda_output` | bool | False | Remove BDA temp files |

#### Audit Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `severity_threshold` | str | "minor" | Minimum severity: minor, major, critical |
| `check_images` | bool | True | Check image accessibility |
| `check_headings` | bool | True | Check heading structure |
| `check_links` | bool | True | Check link text |
| `check_tables` | bool | True | Check table structure |
| `check_forms` | bool | True | Check form controls |
| `check_color_contrast` | bool | True | Check color contrast |
| `rendered` | bool | False | Run browser-backed audit |
| `agent` | bool | False | Use the agent loop (implies rendered) |

#### Remediation Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `auto_fix` | bool | True | Automatically fix issues |
| `fix_images` | bool | True | Fix image issues (alt text) |
| `fix_headings` | bool | True | Fix heading structure |
| `fix_links` | bool | True | Fix link issues |
| `fix_tables` | bool | True | Fix table issues |
| `severity_threshold` | str | "minor" | Minimum severity to fix |
| `max_fixes` | int | None | Limit number of fixes |
| `model_id` | str | (default) | Bedrock model for remediation |
