# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
PDF Report Exporter for Accessibility Reports.

This module provides functionality to export accessibility audit reports,
VPAT reports, and ACR reports to PDF format using FPDF2.
"""

import os
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

from content_accessibility_utility_on_aws.audit.standards import (
    get_criterion_info,
)
from content_accessibility_utility_on_aws.report.scoring import (
    calculate_accessibility_score,
)
from content_accessibility_utility_on_aws.utils.logging_helper import setup_logger

logger = setup_logger(__name__)

# Check for fpdf2 availability
try:
    from fpdf import FPDF
    from fpdf.fonts import FontFace

    FPDF2_AVAILABLE = True
except ImportError:
    FPDF2_AVAILABLE = False
    logger.warning(
        "fpdf2 not installed. PDF export will not be available. "
        "Install with: pip install fpdf2"
    )


# Color definitions (RGB tuples)
COLORS = {
    "primary": (35, 47, 62),       # #232f3e
    "secondary": (255, 153, 0),    # #ff9900
    "success": (40, 167, 69),      # #28a745
    "warning": (255, 193, 7),      # #ffc107
    "danger": (220, 53, 69),       # #dc3545
    "light_gray": (245, 245, 245), # #f5f5f5
    "dark_gray": (102, 102, 102),  # #666666
    "white": (255, 255, 255),
    "black": (0, 0, 0),
}

# Page sizes in mm
PAGE_SIZES = {
    "letter": (215.9, 279.4),
    "a4": (210, 297),
}


class PDFExporter:
    """
    Exporter for generating PDF accessibility reports.

    Supports exporting audit reports, VPAT data, and ACR data to PDF format.
    """

    def __init__(
        self,
        page_size: Tuple = None,
        title: str = "Accessibility Report",
        author: str = "Content Accessibility Utility on AWS",
    ):
        """
        Initialize the PDF exporter.

        Args:
            page_size: Page size tuple in mm (width, height). Default: letter
            title: Document title
            author: Document author
        """
        if not FPDF2_AVAILABLE:
            raise ImportError(
                "fpdf2 is required for PDF export. "
                "Install with: pip install fpdf2"
            )

        self.page_size = page_size or PAGE_SIZES["letter"]
        self.title = title
        self.author = author

    def _create_pdf(self) -> FPDF:
        """Create a new PDF document with standard settings."""
        pdf = FPDF(orientation="P", unit="mm", format=self.page_size)
        pdf.set_auto_page_break(auto=True, margin=20)
        pdf.set_margins(left=19, top=19, right=19)  # ~0.75 inch
        pdf.set_author(self.author)
        pdf.set_title(self.title)
        return pdf

    def _add_title(self, pdf: FPDF, text: str, size: int = 24) -> None:
        """Add a title to the PDF."""
        pdf.set_font("Helvetica", "B", size)
        pdf.set_text_color(*COLORS["primary"])
        pdf.cell(0, 12, text, align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(5)

    def _add_subtitle(self, pdf: FPDF, text: str) -> None:
        """Add a subtitle to the PDF."""
        pdf.set_font("Helvetica", "", 14)
        pdf.set_text_color(*COLORS["dark_gray"])
        pdf.cell(0, 8, text, align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(10)

    def _add_heading1(self, pdf: FPDF, text: str) -> None:
        """Add a level 1 heading."""
        pdf.ln(8)
        pdf.set_font("Helvetica", "B", 16)
        pdf.set_text_color(*COLORS["primary"])
        pdf.cell(0, 10, text, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

    def _add_heading2(self, pdf: FPDF, text: str) -> None:
        """Add a level 2 heading."""
        pdf.ln(5)
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_text_color(*COLORS["primary"])
        pdf.cell(0, 8, text, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

    def _add_heading3(self, pdf: FPDF, text: str) -> None:
        """Add a level 3 heading."""
        pdf.ln(3)
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(*COLORS["dark_gray"])
        pdf.cell(0, 7, text, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)

    def _add_paragraph(self, pdf: FPDF, text: str, size: int = 10) -> None:
        """Add a paragraph of text."""
        pdf.set_font("Helvetica", "", size)
        pdf.set_text_color(*COLORS["black"])
        pdf.multi_cell(0, 5, text)
        pdf.ln(3)

    def _add_small_text(self, pdf: FPDF, text: str) -> None:
        """Add small text."""
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*COLORS["dark_gray"])
        pdf.multi_cell(0, 4, text)
        pdf.ln(2)

    def _add_data_table(
        self,
        pdf: FPDF,
        headers: List[str],
        data: List[List[str]],
        col_widths: Optional[List[int]] = None,
    ) -> None:
        """Add a data table with header row."""
        pdf.set_font("Helvetica", "", 9)

        # Calculate column widths if not provided
        if col_widths is None:
            page_width = self.page_size[0] - 38  # Account for margins
            col_widths = [page_width // len(headers)] * len(headers)

        # Header style
        header_style = FontFace(
            emphasis="BOLD",
            color=COLORS["white"],
            fill_color=COLORS["primary"],
        )

        # Alternating row styles
        row_style_light = FontFace(fill_color=COLORS["white"])
        row_style_dark = FontFace(fill_color=COLORS["light_gray"])

        with pdf.table(
            col_widths=tuple(col_widths),
            borders_layout="ALL",
            cell_fill_color=COLORS["white"],
            cell_fill_mode="ROWS",
            line_height=6,
            text_align="LEFT",
            padding=2,
        ) as table:
            # Header row
            row = table.row()
            for header in headers:
                row.cell(header, style=header_style)

            # Data rows
            for i, data_row in enumerate(data):
                row = table.row()
                style = row_style_dark if i % 2 else row_style_light
                for cell_data in data_row:
                    row.cell(str(cell_data), style=style)

        pdf.ln(5)

    def _add_info_table(self, pdf: FPDF, data: List[List[str]]) -> None:
        """Add a two-column info table (label-value pairs)."""
        pdf.set_font("Helvetica", "", 9)

        page_width = self.page_size[0] - 38
        col_widths = (page_width * 0.3, page_width * 0.7)

        label_style = FontFace(
            emphasis="BOLD",
            color=COLORS["primary"],
            fill_color=COLORS["light_gray"],
        )
        value_style = FontFace(fill_color=COLORS["white"])

        with pdf.table(
            col_widths=col_widths,
            borders_layout="ALL",
            line_height=6,
            text_align="LEFT",
            padding=3,
        ) as table:
            for label, value in data:
                row = table.row()
                row.cell(label, style=label_style)
                row.cell(str(value), style=value_style)

        pdf.ln(5)

    def _add_footer(self, pdf: FPDF) -> None:
        """Add footer to the PDF."""
        pdf.ln(10)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*COLORS["dark_gray"])
        pdf.cell(
            0, 5,
            "Generated by Content Accessibility Utility on AWS",
            align="C",
            new_x="LMARGIN",
            new_y="NEXT"
        )
        pdf.cell(
            0, 5,
            datetime.now().strftime("%B %d, %Y"),
            align="C"
        )

    def export_audit_report(
        self,
        audit_report: Dict[str, Any],
        output_path: str,
        include_details: bool = True,
    ) -> str:
        """
        Export an audit report to PDF.

        Args:
            audit_report: The accessibility audit report
            output_path: Path for the output PDF file
            include_details: Whether to include detailed issue listings

        Returns:
            Path to the generated PDF file
        """
        logger.info(f"Exporting audit report to PDF: {output_path}")

        # Ensure output directory exists
        os.makedirs(
            os.path.dirname(output_path) if os.path.dirname(output_path) else ".",
            exist_ok=True
        )

        pdf = self._create_pdf()
        pdf.add_page()

        # Title section
        self._add_title(pdf, "Accessibility Audit Report")
        html_path = audit_report.get("html_path", "Unknown")
        date_str = datetime.now().strftime("%B %d, %Y")
        self._add_subtitle(pdf, f"File: {html_path}")
        self._add_small_text(pdf, f"Generated: {date_str}")

        # Executive summary
        self._add_heading1(pdf, "Executive Summary")
        # Filter out compliant-* entries - these are positive markers, not issues
        all_issues = audit_report.get("issues", [])
        issues = [i for i in all_issues if not i.get("type", "").startswith("compliant-")]
        total_issues = audit_report.get("total_issues", len(issues))

        severity_counts = {"critical": 0, "major": 0, "minor": 0, "info": 0}
        for issue in issues:
            severity = issue.get("severity", "minor").lower()
            if severity in severity_counts:
                severity_counts[severity] += 1

        summary_text = (
            f"This accessibility audit identified {total_issues} total issues: "
            f"{severity_counts['critical']} critical, "
            f"{severity_counts['major']} major, "
            f"{severity_counts['minor']} minor, and "
            f"{severity_counts['info']} informational."
        )
        self._add_paragraph(pdf, summary_text)

        # Conformance section
        self._add_heading1(pdf, "VPAT Conformance Summary")
        conformance_data = calculate_accessibility_score(issues, target_level="AA")

        self._add_data_table(
            pdf,
            headers=["Conformance Level", "Criteria Count"],
            data=[
                ["Supports", str(conformance_data.get("summary", {}).get("Supports", 0))],
                ["Partially Supports", str(conformance_data.get("summary", {}).get("Partially Supports", 0))],
                ["Does Not Support", str(conformance_data.get("summary", {}).get("Does Not Support", 0))],
            ],
            col_widths=[90, 50],
        )

        # Issues by severity
        self._add_heading1(pdf, "Issues by Severity")
        self._add_data_table(
            pdf,
            headers=["Severity", "Count", "Description"],
            data=[
                ["Critical", str(severity_counts["critical"]),
                 "Issues that prevent access to content"],
                ["Major", str(severity_counts["major"]),
                 "Issues that significantly impact usability"],
                ["Minor", str(severity_counts["minor"]),
                 "Issues that moderately impact usability"],
                ["Info", str(severity_counts["info"]),
                 "Informational findings"],
            ],
            col_widths=[35, 25, 120],
        )

        # Issues by WCAG criterion
        self._add_heading1(pdf, "Issues by WCAG Criterion")
        by_criterion = {}
        for issue in issues:
            criterion = issue.get("wcag_criterion", "Unknown")
            if criterion not in by_criterion:
                by_criterion[criterion] = 0
            by_criterion[criterion] += 1

        if by_criterion:
            criterion_data = []
            for criterion_id in sorted(by_criterion.keys()):
                info = get_criterion_info(criterion_id)
                criterion_data.append([
                    criterion_id,
                    info["name"][:40],
                    str(by_criterion[criterion_id]),
                ])
            self._add_data_table(
                pdf,
                headers=["Criterion", "Name", "Count"],
                data=criterion_data,
                col_widths=[35, 120, 25],
            )
        else:
            self._add_paragraph(pdf, "No issues found.")

        # Detailed issues
        if include_details and issues:
            pdf.add_page()
            self._add_heading1(pdf, "Detailed Issues")

            display_issues = issues[:50]
            for i, issue in enumerate(display_issues, 1):
                severity = issue.get("severity", "minor")
                issue_type = issue.get("type", "unknown")
                message = issue.get("message", "No description")[:200]
                criterion = issue.get("wcag_criterion", "N/A")

                # Set color based on severity
                if severity == "critical":
                    pdf.set_text_color(*COLORS["danger"])
                elif severity == "major":
                    pdf.set_text_color(*COLORS["warning"])
                else:
                    pdf.set_text_color(*COLORS["success"])

                pdf.set_font("Helvetica", "B", 10)
                pdf.cell(0, 6, f"Issue {i}: [{severity.upper()}] {issue_type}",
                        new_x="LMARGIN", new_y="NEXT")

                pdf.set_text_color(*COLORS["dark_gray"])
                pdf.set_font("Helvetica", "", 8)
                pdf.cell(0, 4, f"WCAG: {criterion}", new_x="LMARGIN", new_y="NEXT")

                pdf.set_text_color(*COLORS["black"])
                pdf.set_font("Helvetica", "", 9)
                pdf.multi_cell(0, 4, message)
                pdf.ln(3)

            if len(issues) > 50:
                self._add_small_text(
                    pdf,
                    f"... and {len(issues) - 50} more issues (see full report)"
                )

        # Footer
        self._add_footer(pdf)

        # Save PDF
        pdf.output(output_path)
        logger.info(f"PDF report generated: {output_path}")

        return output_path

    def export_vpat(
        self,
        vpat_data: Dict[str, Any],
        output_path: str,
    ) -> str:
        """
        Export VPAT data to PDF.

        Args:
            vpat_data: The VPAT data dictionary
            output_path: Path for the output PDF file

        Returns:
            Path to the generated PDF file
        """
        logger.info(f"Exporting VPAT to PDF: {output_path}")

        os.makedirs(
            os.path.dirname(output_path) if os.path.dirname(output_path) else ".",
            exist_ok=True
        )

        pdf = self._create_pdf()
        pdf.add_page()

        # Title
        self._add_title(pdf, "Voluntary Product Accessibility Template (VPAT)")
        metadata = vpat_data["metadata"]
        self._add_subtitle(
            pdf,
            f"WCAG {metadata['wcag_version']} Level {metadata['target_level']}"
        )

        # Product information
        self._add_heading1(pdf, "Product Information")
        product = vpat_data["product_info"]
        self._add_info_table(pdf, [
            ["Product Name", product.get("name", "N/A")],
            ["Version", product.get("version", "N/A")],
            ["Vendor", product.get("vendor", "N/A")],
            ["Evaluation Date", product.get("date", "N/A")],
        ])

        # Summary
        self._add_heading1(pdf, "Conformance Summary")
        summary = vpat_data["summary"]
        self._add_info_table(pdf, [
            ["Total Criteria", str(summary["total_criteria"])],
            ["Supports", str(summary["supports"])],
            ["Partially Supports", str(summary["partially_supports"])],
            ["Does Not Support", str(summary["does_not_support"])],
            ["Conformance Rate", f"{summary['conformance_percentage']}%"],
            ["Overall Status", summary["overall_status"]],
        ])

        # Conformance table
        self._add_heading1(pdf, "WCAG 2.1 Conformance Table")

        # Group by principle
        by_principle = {
            "Perceivable": [], "Operable": [],
            "Understandable": [], "Robust": []
        }
        conformance_data = vpat_data["conformance_table"]
        for criterion_id, data in sorted(conformance_data.items()):
            principle = data.get("principle", "Unknown")
            if principle in by_principle:
                by_principle[principle].append(data)

        for principle, criteria in by_principle.items():
            if criteria:
                self._add_heading2(pdf, principle)
                table_data = []
                for c in criteria:
                    table_data.append([
                        f"{c['criterion']} {c['name']} ({c['level']})",
                        c["conformance_label"],
                        str(c["issue_count"]),
                    ])
                self._add_data_table(
                    pdf,
                    headers=["Criterion", "Status", "Issues"],
                    data=table_data,
                    col_widths=[110, 40, 30],
                )

        # Notes
        pdf.add_page()
        self._add_heading1(pdf, "Evaluation Notes")
        notes = vpat_data["notes"]

        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*COLORS["black"])
        pdf.cell(0, 6, "Evaluation Methods:", new_x="LMARGIN", new_y="NEXT")
        self._add_paragraph(pdf, notes["evaluation_methods"])

        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 6, "Assistive Technology:", new_x="LMARGIN", new_y="NEXT")
        self._add_paragraph(pdf, notes["assistive_technology"])

        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 6, "Legal Disclaimer:", new_x="LMARGIN", new_y="NEXT")
        self._add_paragraph(pdf, notes["legal_disclaimer"])

        # Footer
        self._add_footer(pdf)

        pdf.output(output_path)
        logger.info(f"VPAT PDF generated: {output_path}")

        return output_path

    def export_acr(
        self,
        acr_data: Dict[str, Any],
        output_path: str,
    ) -> str:
        """
        Export ACR data to PDF.

        Args:
            acr_data: The ACR data dictionary
            output_path: Path for the output PDF file

        Returns:
            Path to the generated PDF file
        """
        logger.info(f"Exporting ACR to PDF: {output_path}")

        os.makedirs(
            os.path.dirname(output_path) if os.path.dirname(output_path) else ".",
            exist_ok=True
        )

        pdf = self._create_pdf()
        pdf.add_page()

        # Title
        self._add_title(pdf, "Accessibility Conformance Report")
        org = acr_data["organization_info"]
        self._add_subtitle(pdf, f"{org['product']} | {org['name']}")

        # Executive Summary
        self._add_heading1(pdf, "Executive Summary")
        summary = acr_data["executive_summary"]

        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(*COLORS["primary"])
        pdf.cell(
            0, 8,
            f"Overall Status: {summary['overall_status']}",
            new_x="LMARGIN",
            new_y="NEXT"
        )
        self._add_paragraph(pdf, summary["overall_description"])

        # Score summary table
        self._add_data_table(
            pdf,
            headers=["Score", "Grade", "Conforming", "Critical", "Major", "Minor"],
            data=[[
                str(summary["score"]),
                summary["grade"],
                f"{summary['conforming_criteria']}/{summary['total_criteria_evaluated']}",
                str(summary["critical_issues"]),
                str(summary["major_issues"]),
                str(summary["minor_issues"]),
            ]],
            col_widths=[28, 28, 35, 28, 28, 28],
        )

        # Key findings
        self._add_heading2(pdf, "Key Findings")
        for finding in summary["key_findings"][:5]:
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(*COLORS["black"])
            pdf.multi_cell(0, 5, f"  {finding}")
            pdf.ln(1)

        # Findings by principle
        pdf.add_page()
        self._add_heading1(pdf, "Detailed Findings")

        for principle in ["Perceivable", "Operable", "Understandable", "Robust"]:
            principle_findings = acr_data["findings_by_principle"].get(principle, [])
            if principle_findings:
                self._add_heading2(pdf, principle)
                table_data = []
                for f in principle_findings:
                    table_data.append([
                        f"{f['criterion_id']} {f['criterion_name']}",
                        f["status_label"],
                        str(f["issue_count"]),
                    ])
                self._add_data_table(
                    pdf,
                    headers=["Criterion", "Status", "Issues"],
                    data=table_data,
                    col_widths=[110, 40, 30],
                )

        # Recommendations
        pdf.add_page()
        self._add_heading1(pdf, "Prioritized Recommendations")

        for rec in acr_data["recommendations"][:10]:
            self._add_heading3(
                pdf,
                f"#{rec['priority']} [{rec['urgency']}] {rec['criterion']}"
            )
            self._add_paragraph(pdf, rec["description"])
            self._add_small_text(pdf, f"Impact: {rec['impact']}")

        # Methodology
        self._add_heading1(pdf, "Methodology")
        methodology = acr_data["methodology"]

        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*COLORS["black"])
        pdf.cell(0, 6, "Evaluation Method:", new_x="LMARGIN", new_y="NEXT")
        self._add_paragraph(pdf, methodology["evaluation_method"])

        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 6, "Scope:", new_x="LMARGIN", new_y="NEXT")
        self._add_paragraph(pdf, methodology["scope"])

        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 6, "Limitations:", new_x="LMARGIN", new_y="NEXT")
        self._add_paragraph(pdf, methodology["limitations"])

        # Footer
        self._add_footer(pdf)

        pdf.output(output_path)
        logger.info(f"ACR PDF generated: {output_path}")

        return output_path


def export_pdf(
    report_data: Dict[str, Any],
    output_path: str,
    report_type: str = "audit",
    page_size: Tuple = None,
) -> str:
    """
    Export a report to PDF format.

    This is a convenience function that creates a PDFExporter and exports
    the report in a single call.

    Args:
        report_data: The report data dictionary (audit, VPAT, or ACR)
        output_path: Path for the output PDF file
        report_type: Type of report ("audit", "vpat", or "acr")
        page_size: Page size tuple in mm (width, height). Default: letter

    Returns:
        Path to the generated PDF file
    """
    if not FPDF2_AVAILABLE:
        raise ImportError(
            "fpdf2 is required for PDF export. "
            "Install with: pip install fpdf2"
        )

    exporter = PDFExporter(page_size=page_size)

    if report_type == "vpat":
        return exporter.export_vpat(report_data, output_path)
    elif report_type == "acr":
        return exporter.export_acr(report_data, output_path)
    else:
        return exporter.export_audit_report(report_data, output_path)
