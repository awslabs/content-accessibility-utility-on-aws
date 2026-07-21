---
title: Architecture & Core Packages
layout: default
parent: Reference
nav_order: 5
description: "How the four core modules — PDF2HTML, Audit, Remediate, Batch — plus the optional agent layer fit together."
---

<!--
 Copyright 2025 Amazon.com, Inc. or its affiliates.
 SPDX-License-Identifier: Apache-2.0
-->

# Architecture & Core Packages

The package consists of four main modules working together to convert, audit,
remediate, and batch process documents, plus an optional browser-backed **agent**
layer on top.

![Architecture overview: PDF2HTML, Audit, and Remediate feed into the Batch
orchestrator and produce accessible HTML output; the optional Agent layer hangs
off Audit and Remediate to render, fix, re-render, and verify.]({{ '/assets/img/architecture-overview.svg' | relative_url }})

The optional agent layer (`agent/`) renders pages in a real headless browser to
find issues static analysis cannot (computed contrast, focus visibility, the
accessibility tree) and closes the loop by re-rendering to **verify** each fix.
It is fully additive and off by default. See the
[Rendered & Agent Guide](rendered_agent_guide).

## Core Packages

### PDF2HTML

The PDF2HTML module handles conversion of PDF documents to HTML, including image
extraction and processing.

![PDF2HTML flow: a PDF source enters the PDF2HTML module, which runs BDA
integration, image processing, and HTML generation, all producing the HTML
output.]({{ '/assets/img/module-pdf2html.svg' | relative_url }})

Key components:
- Bedrock Data Automation (BDA) integration for PDF parsing
- Image extraction and processing
- HTML structure generation with preserved layout
- Support for both single-page and multi-page output

### Audit

The Audit module analyzes HTML for accessibility issues according to WCAG 2.1 and
2.2 guidelines.

![Audit flow: HTML input enters the Audit module, which runs document,
structure, image, and table checks, all feeding into a single audit
report.]({{ '/assets/img/module-audit.svg' | relative_url }})

Key components:
- Comprehensive accessibility checks
- Issue severity classification
- Detailed context information
- Multiple report formats (HTML, JSON, text)

> **WCAG 2.2 scope:** Because this tool produces static HTML converted from PDFs,
> it audits and remediates the WCAG 2.2 criteria that apply to non-interactive
> documents — currently **2.5.8 Target Size (Minimum)**. The remaining 2.2
> criteria (2.5.7 Dragging Movements, 3.2.6 Consistent Help, 3.3.7 Redundant
> Entry, 3.3.8 Accessible Authentication) govern interactive web-application
> behaviors such as drag gestures, multi-page help, and authentication flows,
> which are out of scope for generated document content.

### Remediate

The Remediate module fixes accessibility issues identified during audit.

![Remediate flow: HTML with issues enters the Remediate module, which applies AI
remediation strategies, direct fixes, and table remediation (direct and
AI-powered), all producing remediated HTML.]({{ '/assets/img/module-remediate.svg' | relative_url }})

Key components:
- AI-powered remediation using Bedrock models
- Direct fixes for common issues
- Advanced table structure remediation
- Image accessibility enhancements
- Remediation reporting

See [Accessibility Remediation](accessibility_remediation) for how each issue
type is fixed.

### Batch

The Batch module provides orchestration for processing documents at scale.

![Batch flow: a document source enters the Batch module, which handles job
management, AWS integration (S3 and DynamoDB), and the processing pipeline
(Lambda), all converging on job completion.]({{ '/assets/img/module-batch.svg' | relative_url }})

Key components:
- AWS service integrations
- Job tracking and status management
- Asynchronous processing
- Lambda function support

The batch stages are wired into the event-driven managed pipeline — see the
[Deployable Pipeline Guide](pipeline_guide).
