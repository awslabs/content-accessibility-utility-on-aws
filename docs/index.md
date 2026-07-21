---
title: Home
layout: default
nav_order: 1
description: "Audit and remediate WCAG 2.1 / 2.2 accessibility issues in documents with generative AI on Amazon Bedrock."
permalink: /
---

<!--
 Copyright 2025 Amazon.com, Inc. or its affiliates.
 SPDX-License-Identifier: Apache-2.0
-->

# Content Accessibility Utility on AWS
{: .fs-9 }

Automatically audit and remediate WCAG 2.1 / 2.2 accessibility issues in your
documents with generative AI on Amazon Bedrock — through a Python **CLI**, a
Python **API**, or a fully managed, event-driven **pipeline**.
{: .fs-6 .fw-300 }

[Get started with the CLI](cli_guide){: .btn .btn-primary .fs-5 .mb-4 .mb-md-0 .mr-2 }
[View on GitHub](https://github.com/awslabs/content-accessibility-utility-on-aws){: .btn .fs-5 .mb-4 .mb-md-0 }

---

## Try it in 2 minutes

The audit path needs only a `pip install` and an HTML file — no AWS account
required:

```bash
pip install content-accessibility-utility-on-aws
content-accessibility-utility-on-aws audit -i page.html -o report.html -f html
```

Open `report.html` for a human-readable accessibility report. Ready for the full
convert → audit → remediate workflow on a PDF? See the
[CLI quickstart](cli_guide#5-minute-quickstart).
{: .note }

## What is this?

The **Content Accessibility Utility on AWS** helps digital-content stakeholders
meet accessibility compliance standards efficiently. It converts PDFs to
accessible HTML, audits HTML against WCAG 2.1 and 2.2, and remediates common
issues using [Amazon Bedrock](https://aws.amazon.com/bedrock/) models — with
batch processing, usage/cost tracking, an optional browser-backed audit + agent
loop, and optional multilingual output.

## Pick the way you want to use it

There are three primary ways to run the solution. Choose the one that matches how
you work, then follow its guide.

| I want to… | Use the… | Guide |
|---|---|---|
| Run one-off or scripted jobs from my terminal | **Command-line interface** | [CLI Guide](cli_guide) |
| Embed audit/remediation into my own Python app | **Python API** | [API Integration Guide](api_integration_guide) |
| Process documents automatically as they land in S3, at scale | **Deployable pipeline** | [Deployable Pipeline Guide](pipeline_guide) |
| Click through a demo web UI | **Streamlit app** | [Streamlit Guide](streamlit_guide) |

### 1. Command-line interface

Install with `pip`, then convert, audit, remediate, translate, or run the full
pipeline against local files. Best for one-off jobs, scripting, and CI.

```bash
pip install content-accessibility-utility-on-aws
content-accessibility-utility-on-aws process -i document.pdf -o output/
```

→ **[CLI Guide](cli_guide)**

### 2. Python API

Call `convert_pdf_to_html()`, `audit_html_accessibility()`,
`remediate_html_accessibility()`, and friends directly from your own code. Best
for embedding accessibility processing into an application or service.

```python
from content_accessibility_utility_on_aws.api import process_pdf_accessibility

result = process_pdf_accessibility(
    pdf_path="document.pdf", output_dir="output/",
    perform_audit=True, perform_remediation=True,
)
```

→ **[API Integration Guide](api_integration_guide)**

### 3. Deployable managed pipeline

Deploy an event-driven pipeline — **upload to S3 → convert → audit →
agent-remediate → accessible result back in S3** — with a single command. No repo
checkout required. Best for hands-off processing at scale.

```bash
pip install "content-accessibility-utility-on-aws[agent]"
content-accessibility-utility-on-aws deploy-pipeline
```

→ **[Deployable Pipeline Guide](pipeline_guide)**

## Explore deeper

- **[Accessibility Remediation](accessibility_remediation)** — how the AI
  remediation works, per-issue strategies, and table handling.
- **[Rendered Audit & Agent Guide](rendered_agent_guide)** — the optional
  browser-backed audit and the render → fix → **verify** agent loop.
- **[Parameter Reference](parameter_reference)** — every parameter, with its CLI
  flag and API equivalent side by side.

## Prerequisites at a glance

- **Python 3.11+**
- An **AWS account** with access to Amazon Bedrock models and (for the PDF path)
  Bedrock Data Automation (BDA).
- An **S3 bucket** for BDA file uploads during PDF conversion.

Full setup lives in each guide. See the [CLI Guide](cli_guide#prerequisites) for
the fastest path to a first run.
{: .tip }

---

Licensed under [Apache-2.0](https://github.com/awslabs/content-accessibility-utility-on-aws/blob/main/LICENSE).
