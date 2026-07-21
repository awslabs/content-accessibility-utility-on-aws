---
title: Get Started
layout: default
nav_order: 2
has_children: true
description: "Choose how to run the solution — CLI, Python API, or the deployable pipeline."
---

<!--
 Copyright 2025 Amazon.com, Inc. or its affiliates.
 SPDX-License-Identifier: Apache-2.0
-->

# Get Started

There are three primary ways to run the solution. Pick the one that matches how
you work, then follow its guide.

| I want to… | Use the… | Guide |
|---|---|---|
| Run one-off or scripted jobs from my terminal | **Command-line interface** | [CLI Guide](cli_guide) |
| Embed audit/remediation into my own Python app | **Python API** | [API Integration Guide](api_integration_guide) |
| Process documents automatically as they land in S3, at scale | **Deployable pipeline** | [Deployable Pipeline Guide](pipeline_guide) |

Prefer to click through a demo UI instead? See the
[Streamlit Guide](streamlit_guide) under **Reference**.

## Fastest path to a first result

If you just want to see it work, install and run the CLI against an HTML file —
no S3 or BDA setup required for the audit path:

```bash
pip install content-accessibility-utility-on-aws
content-accessibility-utility-on-aws audit -i page.html -o report.html -f html
open report.html   # a human-readable accessibility report
```

Then dive into the [CLI Guide](cli_guide) for the full workflow (convert →
audit → remediate), or jump straight to the [Quickstart](cli_guide#5-minute-quickstart).
