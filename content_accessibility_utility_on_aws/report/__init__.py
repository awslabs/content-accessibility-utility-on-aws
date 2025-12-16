# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Report generation module for accessibility audits.

This module provides functionality for generating accessibility reports
in various formats including VPAT, ACR, and PDF.
"""

from content_accessibility_utility_on_aws.report.scoring import (
    calculate_accessibility_score,
    calculate_wcag_compliance,
    get_score_summary,
    SEVERITY_WEIGHTS,
    LEVEL_WEIGHTS,
)

__all__ = [
    "calculate_accessibility_score",
    "calculate_wcag_compliance",
    "get_score_summary",
    "SEVERITY_WEIGHTS",
    "LEVEL_WEIGHTS",
]

# Lazy imports for optional components
def __getattr__(name):
    """Lazy import for optional report generators."""
    if name == "generate_vpat":
        from content_accessibility_utility_on_aws.report.vpat_generator import generate_vpat
        return generate_vpat
    elif name == "generate_acr":
        from content_accessibility_utility_on_aws.report.acr_generator import generate_acr
        return generate_acr
    elif name == "export_pdf":
        from content_accessibility_utility_on_aws.report.pdf_exporter import export_pdf
        return export_pdf
    elif name == "VPATGenerator":
        from content_accessibility_utility_on_aws.report.vpat_generator import VPATGenerator
        return VPATGenerator
    elif name == "ACRGenerator":
        from content_accessibility_utility_on_aws.report.acr_generator import ACRGenerator
        return ACRGenerator
    elif name == "PDFExporter":
        from content_accessibility_utility_on_aws.report.pdf_exporter import PDFExporter
        return PDFExporter
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
