<!--
 Copyright 2025 Amazon.com, Inc. or its affiliates.
 SPDX-License-Identifier: Apache-2.0
-->

# Content Accessibility Utility on AWS

Digital content stakeholders across industries aim to streamline how they meet
accessibility compliance standards efficiently. The **Content Accessibility
Utility on AWS** offers a comprehensive solution for modernizing web content
accessibility with state-of-the-art generative AI models, powered by
[Amazon Bedrock](https://aws.amazon.com/bedrock/). It automatically audits and
remediates WCAG 2.1 and 2.2 accessibility compliance issues, and offers a Python
CLI, a Python API, and a deployable event-driven pipeline. Capabilities include
batch processing for large volumes of content, usage tracking for cost
management, and will continue to expand to support other content types and
modalities.

## 📚 Documentation

**Full documentation is published at
[awslabs.github.io/content-accessibility-utility-on-aws](https://awslabs.github.io/content-accessibility-utility-on-aws/).**

Start there for guides on every way to use the solution:

- **[CLI Guide](https://awslabs.github.io/content-accessibility-utility-on-aws/cli_guide)** — install and run from your terminal
- **[API Integration Guide](https://awslabs.github.io/content-accessibility-utility-on-aws/api_integration_guide)** — embed it in your own Python app
- **[Deployable Pipeline Guide](https://awslabs.github.io/content-accessibility-utility-on-aws/pipeline_guide)** — process documents automatically at scale
- **[Parameter Reference](https://awslabs.github.io/content-accessibility-utility-on-aws/parameter_reference)**, **[Remediation](https://awslabs.github.io/content-accessibility-utility-on-aws/accessibility_remediation)**, **[Rendered Audit & Agent](https://awslabs.github.io/content-accessibility-utility-on-aws/rendered_agent_guide)**, **[Architecture](https://awslabs.github.io/content-accessibility-utility-on-aws/architecture)**, and more.

The documentation source lives in [`docs/`](docs/).

## Features

- Convert PDF documents to accessible HTML, preserving layout and visual appearance
- Extract and embed images
- Audit HTML for WCAG 2.1 and 2.2 accessibility compliance
- Remediate common accessibility issues using Amazon Bedrock models, including
  advanced table remediation strategies
- Optional **browser-backed (rendered) audit** that detects computed-style and
  interactive issues static HTML analysis cannot see (e.g. focus visibility),
  using a real headless browser and [axe-core](https://github.com/dequelabs/axe-core)
- Optional **accessibility agent** ([Strands](https://strandsagents.com)) that
  drives a render → fix → **verify** loop, confirming each fix actually renders
  correctly before marking it resolved
- Optional **internationalization ([i18n])** that translates worked-on content
  into one or more target languages via Amazon Bedrock, preserving markup and
  screen-reader-announced attributes and optionally emitting a single
  multilingual document with an accessible language selector
- Single-page and multi-page output formats
- Batch processing for large-scale document processing
- Detailed usage tracking for BDA pages and Bedrock tokens, plus cost analysis
- Streamlit sample web interface with usage visualization

## Installation

```bash
# From PyPI
pip install content-accessibility-utility-on-aws

# From source
pip install .
```

The core install is static-only (no browser). The rendered audit, the agent, and
translation are opt-in extras so the base footprint stays small:

```bash
pip install "content-accessibility-utility-on-aws[rendered]"   # browser-backed audit
pip install "content-accessibility-utility-on-aws[agent]"      # render -> fix -> verify loop
pip install "content-accessibility-utility-on-aws[i18n]"       # translation + multilingual output
```

The `[rendered]` and `[agent]` extras use a headless browser via
[Playwright](https://playwright.dev/python/); after installing either, run
`playwright install chromium` once. The core package never imports the browser or
agent stack, so static-only workflows are unaffected. See the
[Installation notes](https://awslabs.github.io/content-accessibility-utility-on-aws/cli_guide#installation)
for details.

## Quickstart

The audit path needs only a `pip install` and an HTML file — no AWS account
required:

```bash
pip install content-accessibility-utility-on-aws
content-accessibility-utility-on-aws audit -i page.html -o report.html -f html
```

Open `report.html` for a human-readable accessibility report. For the full
convert → audit → remediate workflow on a PDF (which uses Amazon Bedrock), see
the [CLI quickstart](https://awslabs.github.io/content-accessibility-utility-on-aws/cli_guide#5-minute-quickstart).

## Pick the way you want to use it

| I want to… | Use the… | Guide |
|---|---|---|
| Run one-off or scripted jobs from my terminal | **Command-line interface** | [CLI Guide](https://awslabs.github.io/content-accessibility-utility-on-aws/cli_guide) |
| Embed audit/remediation into my own Python app | **Python API** | [API Integration Guide](https://awslabs.github.io/content-accessibility-utility-on-aws/api_integration_guide) |
| Process documents automatically as they land in S3, at scale | **Deployable pipeline** | [Deployable Pipeline Guide](https://awslabs.github.io/content-accessibility-utility-on-aws/pipeline_guide) |
| Click through a demo web UI | **Streamlit app** | [Streamlit Guide](https://awslabs.github.io/content-accessibility-utility-on-aws/streamlit_guide) |

## Prerequisites

- **Python 3.11+**
- An **AWS account** with access to Amazon Bedrock models and, for the PDF
  conversion path, [Bedrock Data Automation (BDA)](https://aws.amazon.com/bedrock/).
- An **S3 bucket** for BDA file uploads during PDF conversion.

The PDF path reads `BDA_S3_BUCKET` and `BDA_PROJECT_ARN` from the environment (or
accepts `--s3-bucket` / `--bda-project-arn`). Auditing and remediating existing
HTML only needs Bedrock model access. Full setup — creating the S3 bucket and BDA
project, IAM, and configuration files — is in the
[CLI Guide prerequisites](https://awslabs.github.io/content-accessibility-utility-on-aws/cli_guide#prerequisites).

## Architecture

The package consists of four modules — **PDF2HTML**, **Audit**, **Remediate**,
and **Batch** — plus an optional browser-backed **agent** layer.

![Architecture overview: PDF2HTML, Audit, and Remediate feed into the Batch
orchestrator and produce accessible HTML output; the optional Agent layer hangs
off Audit and Remediate to render, fix, re-render, and verify.](https://raw.githubusercontent.com/awslabs/content-accessibility-utility-on-aws/main/docs/assets/img/architecture-overview.svg)

See [Architecture & Core Packages](https://awslabs.github.io/content-accessibility-utility-on-aws/architecture)
for the per-module breakdown and diagrams.

## Requirements

- Python 3.11+
- AWS credentials for Bedrock Data Automation and Bedrock models
- Appropriate IAM permissions for S3 and BDA services

Configure AWS credentials with `aws configure`, environment variables
(`AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`), or a named profile via
`--profile`.

## License

Apache-2.0 License. See [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for
details on how to contribute to this project.
