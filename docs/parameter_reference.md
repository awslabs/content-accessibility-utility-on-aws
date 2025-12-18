<!--
 Copyright 2025 Amazon.com, Inc. or its affiliates.
 SPDX-License-Identifier: Apache-2.0
-->

# Document Accessibility Parameter Reference

This document provides a comprehensive reference for all parameters used in the Document Accessibility tool, ensuring consistent usage between the command-line interface (CLI) and the API.

## Standardized Parameter Names

The following table shows the standardized parameter names used across the tool:

| Parameter | CLI Option | API Parameter | Required | Default | Description |
|-----------|------------|--------------|----------|---------|-------------|
| **Common Parameters** |
| Input Path | `--input`, `-i` | `input_path`, `pdf_path`, `html_path` | Yes | N/A | Path to input file or directory |
| Output Path | `--output`, `-o` | `output_dir`, `output_path` | No | Auto-generated based on input | Path for output files or directory |
| Debug Mode | `--debug` | N/A | No | Disabled | Enable debug logging |
| Quiet Mode | `--quiet`, `-q` | `quiet` | No | Disabled | Suppress non-essential output |
| Config File | `--config`, `-c` | `config_path` | No | None | Path to configuration file |
| Save Config | `--save-config` | N/A | No | None | Save current configuration to file |
| AWS Profile | `--profile` | `profile` | No | Default AWS profile | AWS profile name to use |
| **PDF Conversion** |
| S3 Bucket | `--s3-bucket` | `s3_bucket` | Yes (for PDF processing) | None | Name of S3 bucket for storing input/output files |
| BDA Project ARN | `--bda-project-arn` | `bda_project_arn` | No | None | ARN of an existing BDA project |
| Create BDA Project | `--create-bda-project` | `create_bda_project` | No | Disabled | Create a new BDA project if needed |
| Format | `--format`, `-f` | `format` | No | `html` | Output format (html, md) |
| Single File | `--single-file` | `single_file` | No | Disabled | Generate a single HTML file |
| Single Page | `--single-page` | `single_page` | No | Disabled | Combine pages into one document |
| Multi Page | `--multi-page` | `multi_page` | No | Disabled | Keep pages as separate files |
| Continuous | `--continuous` | `continuous` | No | Disabled | Use continuous scrolling |
| Extract Images | `--extract-images` | `extract_images` | No | Enabled | Extract images from PDF |
| Image Format | `--image-format` | `image_format` | No | `png` | Format for extracted images (png, jpg, webp) |
| Embed Images | `--embed-images` | `embed_images` | No | Disabled | Embed images as data URIs |
| Exclude Images | `--exclude-images` | `exclude_images` | No | Disabled | Don't include images |
| **Accessibility Audit** |
| Format | `--format`, `-f` | `report_format` | No | `json` | Output format for report (json, html, text) |
| Checks | `--checks` | `issue_types` | No | All checks | Comma-separated list of checks to run |
| Severity | `--severity` | `severity_threshold` | No | `minor` | Minimum severity level (minor, major, critical) |
| Detailed | `--detailed` | `detailed`, `include_context` | No | Enabled | Include detailed context information |
| Summary Only | `--summary-only` | `summary_only` | No | Disabled | Only include summary information |
| **Accessibility Remediation** |
| Auto Fix | `--auto-fix` | `auto_fix` | No | Disabled | Automatically fix issues where possible |
| Max Issues | `--max-issues` | `max_issues` | No | All issues | Maximum number of issues to remediate |
| Model ID | `--model-id` | `model_id` | No | Default model | Bedrock model ID to use for remediation |
| Severity Threshold | `--severity-threshold` | `severity_threshold` | No | `minor` | Minimum severity level to remediate |
| Audit Report | `--audit-report` | `audit_report` | No | None | Path to audit report JSON file |
| Generate Report | `--generate-report` | `generate_report` | No | Enabled | Generate a remediation report |
| Report Format | `--report-format` | `report_format` | No | `html` | Format for the remediation report |
| Generate VPAT | `--generate-vpat` | `generate_vpat` | No | Disabled | Generate VPAT on remediated HTML |
| Generate ACR | `--generate-acr` | `generate_acr` | No | Disabled | Generate ACR on remediated HTML |
| Generate PDF | `--generate-pdf` | `generate_pdf` | No | Disabled | Generate PDF versions of reports |
| WCAG Level | `--wcag-level` | `wcag_level` | No | `AA` | Target WCAG level for reports |
| Product Name | `--product-name` | `product_name` | No | Input filename | Product name for reports |
| Product Version | `--product-version` | `product_version` | No | `1.0` | Product version for reports |
| Vendor Name | `--vendor-name` | `vendor_name` | No | None | Vendor name for reports |
| **Accessibility Reports** |
| Generate VPAT | `--generate-vpat` | `generate_vpat` | No | Disabled | Generate VPAT 2.4 report |
| Generate ACR | `--generate-acr` | `generate_acr` | No | Disabled | Generate ACR report |
| Generate PDF | `--generate-pdf` | `generate_pdf` | No | Disabled | Generate PDF versions of reports |
| WCAG Level | `--wcag-level` | `target_level` | No | `AA` | Target WCAG conformance level (A, AA, AAA) |
| Product Name | `--product-name` | `product_info["name"]` | No | Input filename | Product name for reports |
| Product Version | `--product-version` | `product_info["version"]` | No | `1.0` | Product version for reports |
| Vendor Name | `--vendor-name` | `organization_info["name"]` | No | None | Vendor/organization name for reports |
| Product Description | `--product-description` | `product_info["description"]` | No | None | Product description for reports |
| **Process Command** |
| Skip Audit | `--skip-audit` | `perform_audit=False` | No | Disabled | Skip the audit step |
| Skip Remediation | `--skip-remediation` | `perform_remediation=False` | No | Disabled | Skip the remediation step |
| Audit Format | `--audit-format` | `audit_format` | No | `json` | Format for the audit report |
| Report on Remediated | `--report-on-remediated` | `report_on_remediated` | No | Disabled | Generate VPAT/ACR reports based on remediated HTML |
| **Report Command** |
| Report Type | `--type`, `-t` | `report_type` | No | `all` | Report type to generate (vpat, acr, all) |
| Report Format | `--format`, `-f` | `output_format` | No | `html` | Output format (html, json, markdown, pdf) |

## CLI Usage Examples

### Convert a PDF to HTML

```bash
document-accessibility convert --input document.pdf --output output_dir/ --single-file --extract-images
```

### Audit an HTML File

```bash
document-accessibility audit --input document.html --output audit_report.json --format json --severity major
```

### Remediate Accessibility Issues

```bash
document-accessibility remediate --input document.html --output remediated.html --auto-fix --model-id amazon.nova-lite-v1:0
```

### Generate VPAT/ACR Reports

```bash
# Generate all reports from existing audit JSON
document-accessibility report --input audit_report.json --output ./reports

# Generate VPAT only
document-accessibility report --input audit_report.json --type vpat --output ./reports

# Generate ACR as PDF
document-accessibility report --input audit_report.json --type acr --format pdf --output ./reports

# Generate reports with product info
document-accessibility report --input audit_report.json \
    --product-name "My Product" \
    --product-version "2.0" \
    --vendor-name "My Company" \
    --wcag-level AA \
    --output ./reports
```

### Audit with Report Generation

```bash
# Audit and generate VPAT
document-accessibility audit --input document.html --generate-vpat --product-name "My Product"

# Audit with VPAT, ACR, and PDF reports
document-accessibility audit --input document.html \
    --generate-vpat --generate-acr --generate-pdf \
    --product-name "My Product" --vendor-name "My Company"
```

## Process Command (Full Pipeline)

The `process` command combines conversion, auditing, and remediation into a single workflow. It accepts parameters from all three operations, using the following pattern:

```bash
document-accessibility process --input document.pdf --output output_dir/ [options]
```

Common configurations include:

```bash
# Basic process with default settings
document-accessibility process --input document.pdf --output output_dir/

# Process with specific AWS settings
document-accessibility process --input document.pdf --output output_dir/ --s3-bucket my-bucket --profile my-profile

# Process with audit only (no remediation)
document-accessibility process --input document.pdf --output output_dir/ --skip-remediation

# Full processing with custom settings
document-accessibility process --input document.pdf --output output_dir/ --severity major --auto-fix --model-id amazon.nova-lite-v1:0
```

### Remediate with Report Generation

```bash
# Remediate and generate VPAT/ACR on the remediated output
document-accessibility remediate --input document.html --output remediated.html \
    --generate-vpat --generate-acr --product-name "My Product"

# Process with reports on remediated data (shows improvement)
document-accessibility process --input document.pdf --output output_dir/ \
    --generate-vpat --generate-acr --report-on-remediated \
    --product-name "My Product" --vendor-name "My Company"
```

## Parameter Value Standards

### Severity Levels

The standardized severity levels are:
- `minor`: Low-impact issues that should be fixed but don't severely impact accessibility
- `major`: Medium-impact issues that significantly affect accessibility for some users
- `critical`: High-impact issues that make content completely inaccessible to certain users

### Issue Types

Common issue types include:
- `missing-alt-text`: Images without alternative text
- `empty-alt-text`: Images with empty alt text
- `generic-alt-text`: Images with generic/uninformative alt text
- `contrast`: Insufficient color contrast
- `heading-structure`: Improper heading structure or nesting
- `missing-labels`: Form controls without labels
- `missing-lang`: Missing language declaration
- `empty-links`: Links with no text content
- `table-structure`: Tables without proper headers or structure
- `document-structure`: Issues with overall document structure and landmarks

## Python API Examples

### Full Processing Pipeline

```python
from document_accessibility.api import process_pdf_accessibility

# Process a PDF through the full pipeline
result = process_pdf_accessibility(
    pdf_path="document.pdf",
    output_dir="output/",
    conversion_options={
        "single_file": True,
        "image_format": "png"
    },
    audit_options={
        "severity_threshold": "minor",
        "detailed": True
    },
    remediation_options={
        "model_id": "amazon.nova-lite-v1:0",
        "auto_fix": True
    },
    perform_audit=True,
    perform_remediation=True
)
```

### Individual Components

```python
from document_accessibility.api import (
    convert_pdf_to_html,
    audit_html_accessibility,
    remediate_html_accessibility
)

# Convert PDF to HTML
conversion_result = convert_pdf_to_html(
    pdf_path="document.pdf",
    output_dir="output/",
    options={
        "single_file": True,
        "image_format": "png"
    }
)

# Audit HTML for accessibility issues
audit_result = audit_html_accessibility(
    html_path="output/document.html",
    options={
        "severity_threshold": "minor",
        "detailed": True
    }
)

# Remediate accessibility issues
remediation_result = remediate_html_accessibility(
    html_path="output/document.html",
    audit_report=audit_result,
    options={
        "model_id": "amazon.nova-lite-v1:0",
        "auto_fix": True
    }
)
```

## Environment Variables

The tool supports configuration through the following environment variables:

| Variable | Description | Required |
|----------|-------------|----------|
| `BDA_S3_BUCKET` or `DOCUMENT_ACCESSIBILITY_S3_BUCKET` | S3 bucket name for storing input/output files | Yes |
| `BDA_PROJECT_ARN` or `DOCUMENT_ACCESSIBILITY_BDA_PROJECT_ARN` | ARN for the BDA project | Yes |
| `AWS_PROFILE` | AWS profile to use for credentials | No |
| `CONTENT_ACCESSIBILITY_WORK_DIR` | Directory for temporary files | No |

Ensure these variables are set before running the tool.

## Streamlit Interface Options

When using the Streamlit web interface, options are configured through the UI rather than command line parameters. The interface provides similar functionality with an intuitive web-based experience.
