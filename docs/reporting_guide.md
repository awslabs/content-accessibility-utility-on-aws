<!--
 Copyright 2025 Amazon.com, Inc. or its affiliates.
 SPDX-License-Identifier: Apache-2.0
-->

# Accessibility Reporting Guide

This guide provides comprehensive documentation for the Report module, which enables generation of accessibility reports in various formats including VPAT, ACR, and PDF.

## Table of Contents

- [Overview](#overview)
- [CLI Usage](#cli-usage)
  - [Report Command](#report-command)
  - [Audit with Reports](#audit-with-reports)
  - [Process with Reports](#process-with-reports)
  - [Reports on Remediated Data](#reports-on-remediated-data)
- [Accessibility Scoring](#accessibility-scoring)
  - [Score Calculation](#score-calculation)
  - [Letter Grades](#letter-grades)
  - [WCAG Compliance Checking](#wcag-compliance-checking)
- [VPAT Generation](#vpat-generation)
  - [What is VPAT?](#what-is-vpat)
  - [VPAT Structure](#vpat-structure)
  - [Generating VPAT Reports](#generating-vpat-reports)
- [ACR Generation](#acr-generation)
  - [What is ACR?](#what-is-acr)
  - [ACR Structure](#acr-structure)
  - [Generating ACR Reports](#generating-acr-reports)
- [PDF Export](#pdf-export)
- [Output Formats](#output-formats)
- [API Reference](#api-reference)

## Overview

The Report module provides tools for generating comprehensive accessibility reports based on audit results. It supports:

- **Accessibility Scoring**: Calculate compliance scores with letter grades
- **VPAT Reports**: Generate Voluntary Product Accessibility Template (VPAT) 2.4 format reports
- **ACR Reports**: Create detailed Accessibility Conformance Reports
- **PDF Export**: Export reports to professional PDF documents

All report generators work with audit results from the Audit module and can output in multiple formats (HTML, JSON, Markdown, PDF).

## CLI Usage

The CLI provides multiple ways to generate reports from the command line.

### Report Command

The `report` command generates VPAT/ACR reports from an existing audit JSON file:

```bash
# Generate all reports (VPAT + ACR) in HTML format
accessibility report -i audit_report.json -o ./reports

# Generate only VPAT report
accessibility report -i audit_report.json -t vpat -o ./reports

# Generate only ACR report
accessibility report -i audit_report.json -t acr -o ./reports

# Generate reports in different formats
accessibility report -i audit_report.json -f json -o ./reports
accessibility report -i audit_report.json -f markdown -o ./reports
accessibility report -i audit_report.json -f pdf -o ./reports

# Customize product information
accessibility report -i audit_report.json \
    --product-name "My Application" \
    --product-version "2.0" \
    --vendor-name "My Company" \
    -o ./reports

# Target different WCAG conformance levels
accessibility report -i audit_report.json --wcag-level AAA -o ./reports
```

#### Report Command Options

| Option | Description | Default |
|--------|-------------|---------|
| `-i, --input` | Input audit report JSON file (required) | - |
| `-o, --output` | Output directory for reports | Current directory |
| `-t, --type` | Report type: `vpat`, `acr`, or `all` | `all` |
| `-f, --format` | Output format: `html`, `json`, `markdown`, `pdf` | `html` |
| `--wcag-level` | Target WCAG level: `A`, `AA`, `AAA` | `AA` |
| `--product-name` | Product name for reports | `Product` |
| `--product-version` | Product version | `1.0` |
| `--vendor-name` | Vendor/organization name | - |
| `--product-description` | Product description | - |

### Audit with Reports

Generate reports directly during an audit:

```bash
# Audit and generate VPAT report
accessibility audit -i document.html --generate-vpat

# Audit and generate ACR report
accessibility audit -i document.html --generate-acr

# Audit and generate both VPAT and ACR
accessibility audit -i document.html --generate-vpat --generate-acr

# Also generate PDF versions
accessibility audit -i document.html --generate-vpat --generate-acr --generate-pdf

# Customize product info during audit
accessibility audit -i document.html \
    --generate-vpat \
    --generate-acr \
    --product-name "My Product" \
    --product-version "1.0" \
    --vendor-name "My Company" \
    --wcag-level AA
```

#### Audit Report Options

| Option | Description |
|--------|-------------|
| `--generate-vpat` | Generate VPAT 2.4 report alongside audit |
| `--generate-acr` | Generate ACR report alongside audit |
| `--generate-pdf` | Generate PDF versions of reports |
| `--wcag-level` | Target WCAG level for reports (`A`, `AA`, `AAA`) |
| `--product-name` | Product name for reports |
| `--product-version` | Product version for reports |
| `--vendor-name` | Vendor/organization name for reports |

### Process with Reports

Generate reports as part of the full PDF processing pipeline:

```bash
# Full workflow: convert PDF, audit, remediate, and generate VPAT
accessibility process -i document.pdf -o ./output --generate-vpat

# Full workflow with both VPAT and ACR reports
accessibility process -i document.pdf -o ./output \
    --generate-vpat \
    --generate-acr

# Full workflow with all reports including PDFs
accessibility process -i document.pdf -o ./output \
    --generate-vpat \
    --generate-acr \
    --generate-pdf \
    --product-name "My Document" \
    --vendor-name "My Organization"
```

#### Output Files

When using the process command with report options, the following files are generated:

```
output/
├── html/                    # Converted HTML files
│   └── document.html
├── audit_report.json        # Audit results
├── remediated_document.html # Remediated HTML
├── remediation_report.html  # Remediation report
├── vpat_report.html         # VPAT report (if --generate-vpat)
├── vpat_report.pdf          # VPAT PDF (if --generate-pdf)
├── acr_report.html          # ACR report (if --generate-acr)
└── acr_report.pdf           # ACR PDF (if --generate-pdf)
```

### Reports on Remediated Data

Generate reports that reflect the accessibility state after remediation. This is useful for showing improvement in accessibility compliance.

#### Process Command with Remediated Reports

```bash
# Generate reports based on remediated HTML (shows improved state)
accessibility process -i document.pdf -o ./output \
    --generate-vpat \
    --generate-acr \
    --report-on-remediated \
    --product-name "My Document" \
    --vendor-name "My Organization"
```

#### Remediate Command with Reports

```bash
# Remediate and generate reports on the improved HTML
accessibility remediate -i document.html -o remediated.html \
    --generate-vpat \
    --generate-acr \
    --product-name "My Document" \
    --vendor-name "My Organization"
```

#### Output Files with Remediated Reports

When using `--report-on-remediated` with process or the report options with remediate:

```
output/
├── html/                          # Converted HTML files
├── audit_report.json              # Initial audit results
├── remediated_document.html       # Remediated HTML
├── remediation_report.html        # Remediation details
├── remediated_audit_report.json   # Re-audit of remediated HTML
├── vpat_remediated_report.html    # VPAT based on remediated state
├── vpat_remediated_report.pdf     # VPAT PDF (if --generate-pdf)
├── acr_remediated_report.html     # ACR based on remediated state
└── acr_remediated_report.pdf      # ACR PDF (if --generate-pdf)
```

The CLI will show the remediation impact:

```
Remediation Impact:
  Original issues: 25
  Remaining issues: 8
  Issues resolved: 17
```

## Accessibility Scoring

### Score Calculation

The scoring system calculates an accessibility score (0-100) based on the severity and WCAG level of identified issues.

```python
from content_accessibility_utility_on_aws.report import calculate_accessibility_score

# Calculate score from audit issues
score_result = calculate_accessibility_score(audit_result["issues"])

# Output structure:
# {
#     "score": 85.5,
#     "grade": "B",
#     "max_score": 100,
#     "deductions": 14.5,
#     "issues_counted": 5,
#     "breakdown": {
#         "by_severity": {"critical": 0, "major": 2, "minor": 3, "info": 0},
#         "by_level": {"A": 1, "AA": 3, "AAA": 1}
#     },
#     "compliance_status": "Substantially compliant",
#     "details": {
#         "critical_issues": 0,
#         "major_issues": 2,
#         "minor_issues": 3,
#         "info_issues": 0
#     }
# }
```

#### Severity Weights

Issues are weighted by severity for score calculation:

| Severity | Weight | Description |
|----------|--------|-------------|
| Critical | 15 | Prevents access to content for users with disabilities |
| Major | 8 | Significantly impacts usability |
| Minor | 3 | Moderately impacts usability |
| Info | 0 | Informational, no score impact |

#### WCAG Level Multipliers

Weights are adjusted based on WCAG conformance level:

| Level | Multiplier | Description |
|-------|------------|-------------|
| A | 1.5x | Most fundamental accessibility requirements |
| AA | 1.2x | Standard compliance target |
| AAA | 1.0x | Enhanced accessibility (not required for compliance) |

### Letter Grades

Scores are converted to letter grades:

| Score Range | Grade | Status |
|-------------|-------|--------|
| 90-100 | A | Fully compliant |
| 80-89 | B | Substantially compliant |
| 70-79 | C | Partially compliant |
| 60-69 | D | Minimally compliant |
| 0-59 | F | Non-compliant |

### WCAG Compliance Checking

Check compliance at specific WCAG levels:

```python
from content_accessibility_utility_on_aws.report import calculate_wcag_compliance

# Check Level AA compliance
compliance = calculate_wcag_compliance(
    issues=audit_result["issues"],
    target_level="AA"  # Options: "A", "AA", "AAA"
)

# Output structure:
# {
#     "compliant": False,
#     "target_level": "AA",
#     "criteria_with_issues": 3,
#     "total_issues_at_level": 5,
#     "issues_by_criterion": {"1.1.1": 2, "1.4.3": 2, "2.4.4": 1},
#     "failing_criteria": ["1.1.1", "1.4.3", "2.4.4"]
# }
```

## VPAT Generation

### What is VPAT?

VPAT (Voluntary Product Accessibility Template) is an industry-standard document that vendors use to self-disclose the accessibility of their products. It's commonly required for:

- Government procurement (Section 508)
- Enterprise software purchases
- Educational institution compliance
- Healthcare system acquisitions

The Report module generates VPAT 2.4 WCAG format reports.

### VPAT Structure

A generated VPAT report includes:

1. **Product Information**: Name, version, vendor, evaluation date
2. **Conformance Summary**: Overview of compliance status
3. **Conformance Table**: Detailed status for each WCAG criterion
4. **Evaluation Notes**: Methodology, limitations, disclaimers

### Generating VPAT Reports

```python
from content_accessibility_utility_on_aws.report.vpat_generator import (
    VPATGenerator,
    generate_vpat
)

# Method 1: Using convenience function
vpat_data = generate_vpat(
    audit_report=audit_result,
    output_path="reports/vpat.html",
    output_format="html",  # Options: "html", "json", "markdown"
    product_info={
        "name": "My Application",
        "version": "2.0.1",
        "vendor": "My Company Inc.",
        "contact": "accessibility@mycompany.com",
        "website": "https://mycompany.com",
        "description": "Enterprise web application",
        "date": "2024-01-15"
    },
    target_level="AA"  # Options: "A", "AA", "AAA"
)

# Method 2: Using VPATGenerator class
generator = VPATGenerator(
    product_info={"name": "My App", "version": "1.0"},
    target_level="AA"
)

# Generate in multiple formats
vpat_html = generator.generate(audit_result, "reports/vpat.html", "html")
vpat_json = generator.generate(audit_result, "reports/vpat.json", "json")
vpat_md = generator.generate(audit_result, "reports/vpat.md", "markdown")
```

#### VPAT Conformance Levels

Each criterion is evaluated against these conformance levels:

| Level | Description |
|-------|-------------|
| Supports | Meets criterion without known defects |
| Partially Supports | Some functionality does not meet criterion |
| Does Not Support | Majority of functionality does not meet criterion |
| Not Applicable | Criterion is not relevant to the product |
| Not Evaluated | Product has not been evaluated against criterion |

## ACR Generation

### What is ACR?

ACR (Accessibility Conformance Report) is a detailed document that provides comprehensive accessibility compliance information. It's more detailed than a VPAT and includes:

- Executive summary with key findings
- Prioritized recommendations
- Remediation guidance
- Detailed findings by WCAG principle

### ACR Structure

A generated ACR report includes:

1. **Executive Summary**: Overall status, score, key findings
2. **Score & Compliance**: Numeric score, grade, compliance status
3. **Findings by Principle**: Detailed findings organized by WCAG principle
4. **Recommendations**: Prioritized list of remediation actions
5. **Methodology**: Evaluation methods and limitations
6. **Appendix**: Detailed issue listings and glossary

### Generating ACR Reports

```python
from content_accessibility_utility_on_aws.report.acr_generator import (
    ACRGenerator,
    generate_acr
)

# Method 1: Using convenience function
acr_data = generate_acr(
    audit_report=audit_result,
    output_path="reports/acr.html",
    output_format="html",
    organization_info={
        "name": "My Organization",
        "product": "Enterprise Portal",
        "url": "https://portal.myorg.com",
        "evaluator": "Accessibility Team",
        "contact": "accessibility@myorg.com",
        "scope": "Full application audit"
    },
    target_level="AA",
    include_remediation_guidance=True
)

# Access the executive summary
summary = acr_data["executive_summary"]
print(f"Overall Status: {summary['overall_status']}")
print(f"Score: {summary['score']}, Grade: {summary['grade']}")

# Access recommendations
for rec in acr_data["recommendations"][:5]:
    print(f"#{rec['priority']} [{rec['urgency']}] {rec['criterion']}")

# Method 2: Using ACRGenerator class
generator = ACRGenerator(
    organization_info={"name": "My Org", "product": "My App"},
    target_level="AA",
    include_remediation_guidance=True
)

acr = generator.generate(audit_result, "reports/acr.html", "html")
```

#### ACR Executive Summary

The executive summary provides:

- **Overall Status**: Conforms, Partially Conforms, Does Not Conform
- **Score and Grade**: Numeric score (0-100) and letter grade
- **Issue Counts**: Critical, major, and minor issue totals
- **Key Findings**: Top issues requiring attention
- **Conforming Criteria Count**: How many criteria pass vs fail

## PDF Export

Export reports to professional PDF format using FPDF2:

```python
from content_accessibility_utility_on_aws.report.pdf_exporter import (
    PDFExporter,
    export_pdf,
    PAGE_SIZES,  # Contains "letter" and "a4" page sizes in mm
)

# Export audit report
export_pdf(
    report_data=audit_result,
    output_path="reports/audit.pdf",
    report_type="audit",
    page_size=PAGE_SIZES["letter"]  # Options: PAGE_SIZES["letter"], PAGE_SIZES["a4"]
)

# Export VPAT report
export_pdf(
    report_data=vpat_data,
    output_path="reports/vpat.pdf",
    report_type="vpat"
)

# Export ACR report
export_pdf(
    report_data=acr_data,
    output_path="reports/acr.pdf",
    report_type="acr"
)

# Using PDFExporter class for more control
exporter = PDFExporter(
    page_size=PAGE_SIZES["letter"],
    title="Accessibility Assessment",
    author="Accessibility Team"
)

# Export with options
exporter.export_audit_report(
    audit_report=audit_result,
    output_path="reports/detailed_audit.pdf",
    include_details=True  # Include full issue listings
)
```

### PDF Features

- Professional styling with company colors
- Color-coded severity indicators
- Executive summary pages
- Detailed issue tables
- Page numbers and headers
- Print-ready formatting

## Output Formats

All generators support multiple output formats:

| Format | Extension | Use Case |
|--------|-----------|----------|
| HTML | `.html` | Interactive viewing, web publishing |
| JSON | `.json` | Machine processing, data integration |
| Markdown | `.md` | Documentation, version control |
| PDF | `.pdf` | Professional distribution, printing |

### Format Examples

```python
# HTML - Interactive report with styling
generate_vpat(audit_result, "report.html", "html")

# JSON - Machine-readable data
generate_vpat(audit_result, "report.json", "json")

# Markdown - Documentation-friendly
generate_vpat(audit_result, "report.md", "markdown")

# PDF - Print-ready document
export_pdf(vpat_data, "report.pdf", "vpat")
```

## API Reference

### Scoring Functions

| Function | Description |
|----------|-------------|
| `calculate_accessibility_score(issues, max_score=100)` | Calculate score with grade |
| `calculate_wcag_compliance(issues, target_level="AA")` | Check WCAG compliance |
| `get_score_summary(audit_report)` | Get comprehensive score summary |

### VPAT Generator

| Method | Description |
|--------|-------------|
| `VPATGenerator(product_info, target_level)` | Initialize generator |
| `generate(audit_report, output_path, output_format)` | Generate VPAT |
| `generate_vpat(...)` | Convenience function |

### ACR Generator

| Method | Description |
|--------|-------------|
| `ACRGenerator(organization_info, target_level, include_remediation_guidance)` | Initialize generator |
| `generate(audit_report, output_path, output_format)` | Generate ACR |
| `generate_acr(...)` | Convenience function |

### PDF Exporter

| Method | Description |
|--------|-------------|
| `PDFExporter(page_size, title, author)` | Initialize exporter |
| `export_audit_report(audit_report, output_path, include_details)` | Export audit PDF |
| `export_vpat(vpat_data, output_path)` | Export VPAT PDF |
| `export_acr(acr_data, output_path)` | Export ACR PDF |
| `export_pdf(...)` | Convenience function |

## Complete Example

Here's a complete workflow for generating all report types:

```python
from content_accessibility_utility_on_aws.api import audit_html_accessibility
from content_accessibility_utility_on_aws.report import (
    calculate_accessibility_score,
    get_score_summary
)
from content_accessibility_utility_on_aws.report.vpat_generator import generate_vpat
from content_accessibility_utility_on_aws.report.acr_generator import generate_acr
from content_accessibility_utility_on_aws.report.pdf_exporter import export_pdf
import os

def generate_all_reports(html_path, output_dir, product_info):
    """Generate comprehensive accessibility reports."""

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)

    # Run audit
    audit_result = audit_html_accessibility(html_path)

    # Calculate score
    score = calculate_accessibility_score(audit_result["issues"])
    print(f"Accessibility Score: {score['score']} ({score['grade']})")

    # Generate VPAT
    vpat = generate_vpat(
        audit_result,
        f"{output_dir}/vpat.html",
        "html",
        product_info=product_info,
        target_level="AA"
    )

    # Generate ACR
    acr = generate_acr(
        audit_result,
        f"{output_dir}/acr.html",
        "html",
        organization_info={
            "name": product_info.get("vendor", ""),
            "product": product_info.get("name", "")
        },
        target_level="AA"
    )

    # Export PDFs
    export_pdf(audit_result, f"{output_dir}/audit.pdf", "audit")
    export_pdf(vpat, f"{output_dir}/vpat.pdf", "vpat")
    export_pdf(acr, f"{output_dir}/acr.pdf", "acr")

    # Also generate JSON for archival
    generate_vpat(audit_result, f"{output_dir}/vpat.json", "json", product_info)
    generate_acr(audit_result, f"{output_dir}/acr.json", "json")

    return {
        "score": score,
        "vpat": vpat,
        "acr": acr,
        "output_dir": output_dir
    }

# Usage
results = generate_all_reports(
    html_path="document.html",
    output_dir="accessibility_reports",
    product_info={
        "name": "My Product",
        "version": "1.0",
        "vendor": "My Company"
    }
)
```
