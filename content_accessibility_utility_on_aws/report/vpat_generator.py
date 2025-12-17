# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
VPAT (Voluntary Product Accessibility Template) Report Generator.

This module generates VPAT 2.4 WCAG format reports for accessibility audits.
VPAT is an industry-standard format for documenting accessibility conformance.
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Any, Optional

from content_accessibility_utility_on_aws.audit.standards import (
    get_criteria_for_level,
)
from content_accessibility_utility_on_aws.utils.logging_helper import setup_logger

logger = setup_logger(__name__)


# VPAT Conformance Level descriptions
CONFORMANCE_LEVELS = {
    "supports": "The functionality of the product has at least one method that meets the criterion without known defects or meets with equivalent facilitation.",
    "partially_supports": "Some functionality of the product does not meet the criterion.",
    "does_not_support": "The majority of product functionality does not meet the criterion.",
    "not_applicable": "The criterion is not relevant to the product.",
    "not_evaluated": "The product has not been evaluated against the criterion.",
}

# Short conformance level labels
CONFORMANCE_LABELS = {
    "supports": "Supports",
    "partially_supports": "Partially Supports",
    "does_not_support": "Does Not Support",
    "not_applicable": "Not Applicable",
    "not_evaluated": "Not Evaluated",
}


class VPATGenerator:
    """
    Generator for VPAT 2.4 WCAG format reports.

    The VPAT (Voluntary Product Accessibility Template) is a document
    that vendors use to self-disclose the accessibility of their products.
    """

    def __init__(
        self,
        product_info: Optional[Dict[str, str]] = None,
        target_level: str = "AA",
    ):
        """
        Initialize the VPAT generator.

        Args:
            product_info: Dictionary containing product information
            target_level: Target WCAG conformance level (A, AA, or AAA)
        """
        self.product_info = product_info or {}
        self.target_level = target_level.upper()
        self.criteria = get_criteria_for_level(self.target_level)

    def generate(
        self,
        audit_report: Dict[str, Any],
        output_path: Optional[str] = None,
        output_format: str = "html",
    ) -> Dict[str, Any]:
        """
        Generate a VPAT report from an audit report.

        Args:
            audit_report: The accessibility audit report
            output_path: Path to save the report (optional)
            output_format: Output format (html, json, or markdown)

        Returns:
            Dictionary containing the VPAT data
        """
        logger.info(f"Generating VPAT report for level {self.target_level}")

        # Build conformance data from audit results
        conformance_data = self._build_conformance_data(audit_report)

        # Create the VPAT structure
        vpat_data = {
            "metadata": {
                "vpat_version": "2.4",
                "wcag_version": "2.1",
                "target_level": self.target_level,
                "evaluation_date": datetime.now().isoformat(),
                "generator": "Content Accessibility Utility on AWS",
            },
            "product_info": self._get_product_info(),
            "summary": self._generate_summary(conformance_data),
            "conformance_table": conformance_data,
            "notes": self._generate_notes(audit_report),
        }

        # Write output if path provided
        if output_path:
            if output_format == "html":
                self._write_html(vpat_data, output_path)
            elif output_format == "json":
                self._write_json(vpat_data, output_path)
            elif output_format == "markdown":
                self._write_markdown(vpat_data, output_path)
            else:
                logger.warning(f"Unknown format {output_format}, using HTML")
                self._write_html(vpat_data, output_path)

        return vpat_data

    def _get_product_info(self) -> Dict[str, str]:
        """Get product information with defaults."""
        return {
            "name": self.product_info.get("name", "Product Name"),
            "version": self.product_info.get("version", "1.0"),
            "vendor": self.product_info.get("vendor", ""),
            "contact": self.product_info.get("contact", ""),
            "website": self.product_info.get("website", ""),
            "description": self.product_info.get("description", ""),
            "date": self.product_info.get("date", datetime.now().strftime("%Y-%m-%d")),
        }

    def _build_conformance_data(
        self, audit_report: Dict[str, Any]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Build conformance data by mapping audit issues to WCAG criteria.

        Args:
            audit_report: The accessibility audit report

        Returns:
            Dictionary mapping criterion IDs to conformance data
        """
        # Group issues by WCAG criterion
        issues_by_criterion = {}
        for issue in audit_report.get("issues", []):
            criterion = issue.get("wcag_criterion", "")
            if criterion:
                if criterion not in issues_by_criterion:
                    issues_by_criterion[criterion] = []
                issues_by_criterion[criterion].append(issue)

        # Build conformance data for each criterion
        conformance_data = {}
        for criterion_id, criterion_info in self.criteria.items():
            issues = issues_by_criterion.get(criterion_id, [])

            # Determine conformance level based on issues
            conformance_level = self._determine_conformance_level(issues)

            # Build remarks from issues
            remarks = self._build_remarks(issues, criterion_info)

            conformance_data[criterion_id] = {
                "criterion": criterion_id,
                "name": criterion_info["name"],
                "level": criterion_info["level"],
                "principle": criterion_info["principle"],
                "guideline": criterion_info["guideline"],
                "conformance_level": conformance_level,
                "conformance_label": CONFORMANCE_LABELS.get(
                    conformance_level, "Not Evaluated"
                ),
                "remarks": remarks,
                "issue_count": len(issues),
            }

        return conformance_data

    def _determine_conformance_level(self, issues: List[Dict[str, Any]]) -> str:
        """
        Determine conformance level based on issues found.

        Args:
            issues: List of issues for a criterion

        Returns:
            Conformance level string
        """
        if not issues:
            return "supports"

        # Check if any issues remain unremediated
        unremediated = [
            i for i in issues
            if i.get("remediation_status", "needs_remediation") != "remediated"
        ]

        if not unremediated:
            return "supports"

        # Count by severity
        critical_count = sum(1 for i in unremediated if i.get("severity") == "critical")
        major_count = sum(1 for i in unremediated if i.get("severity") == "major")
        minor_count = sum(1 for i in unremediated if i.get("severity") == "minor")

        # Determine conformance level based on severity distribution
        if critical_count > 0:
            return "does_not_support"
        elif major_count > 2:
            return "does_not_support"
        elif major_count > 0 or minor_count > 2:
            return "partially_supports"
        else:
            return "partially_supports"

    def _build_remarks(
        self, issues: List[Dict[str, Any]], criterion_info: Dict[str, str]
    ) -> str:
        """
        Build remarks text from issues.

        Args:
            issues: List of issues
            criterion_info: Criterion information

        Returns:
            Remarks text
        """
        if not issues:
            return f"No issues found for {criterion_info['name']}."

        # Group issues by type
        issue_types = {}
        for issue in issues:
            issue_type = issue.get("type", "unknown")
            if issue_type not in issue_types:
                issue_types[issue_type] = 0
            issue_types[issue_type] += 1

        # Build remarks
        remarks_parts = []
        for issue_type, count in issue_types.items():
            if count == 1:
                remarks_parts.append(f"1 {issue_type.replace('-', ' ')} issue")
            else:
                remarks_parts.append(f"{count} {issue_type.replace('-', ' ')} issues")

        return "Found: " + ", ".join(remarks_parts) + "."

    def _generate_summary(
        self, conformance_data: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Generate summary statistics from conformance data.

        Args:
            conformance_data: The conformance data dictionary

        Returns:
            Summary statistics
        """
        total = len(conformance_data)
        supports = sum(
            1 for c in conformance_data.values()
            if c["conformance_level"] == "supports"
        )
        partial = sum(
            1 for c in conformance_data.values()
            if c["conformance_level"] == "partially_supports"
        )
        does_not = sum(
            1 for c in conformance_data.values()
            if c["conformance_level"] == "does_not_support"
        )
        na = sum(
            1 for c in conformance_data.values()
            if c["conformance_level"] == "not_applicable"
        )

        # Calculate conformance percentage
        applicable = total - na
        if applicable > 0:
            conformance_pct = round((supports / applicable) * 100, 1)
        else:
            conformance_pct = 100.0

        return {
            "total_criteria": total,
            "supports": supports,
            "partially_supports": partial,
            "does_not_support": does_not,
            "not_applicable": na,
            "conformance_percentage": conformance_pct,
            "overall_status": self._get_overall_status(supports, partial, does_not, applicable),
        }

    def _get_overall_status(
        self, supports: int, partial: int, does_not: int, applicable: int
    ) -> str:
        """Get overall conformance status."""
        if applicable == 0:
            return "Not Applicable"
        if does_not > 0:
            return "Does Not Conform"
        if partial > 0:
            return "Partially Conforms"
        return "Fully Conforms"

    def _generate_notes(self, audit_report: Dict[str, Any]) -> Dict[str, str]:
        """Generate notes section."""
        return {
            "evaluation_methods": (
                "Automated accessibility testing using Content Accessibility Utility on AWS. "
                "Manual testing may reveal additional issues not detected by automated tools."
            ),
            "assistive_technology": (
                "This evaluation focuses on WCAG 2.1 conformance. "
                "Compatibility with specific assistive technologies was not directly tested."
            ),
            "legal_disclaimer": (
                "This VPAT is provided for informational purposes only. "
                "The information contained herein is subject to change without notice. "
                "Complete conformance requires both automated and manual accessibility testing."
            ),
        }

    def _write_html(self, vpat_data: Dict[str, Any], output_path: str) -> None:
        """Write VPAT data as HTML."""
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)

        html = self._generate_html(vpat_data)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)
        logger.info(f"VPAT HTML report written to {output_path}")

    def _write_json(self, vpat_data: Dict[str, Any], output_path: str) -> None:
        """Write VPAT data as JSON."""
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(vpat_data, f, indent=2)
        logger.info(f"VPAT JSON report written to {output_path}")

    def _write_markdown(self, vpat_data: Dict[str, Any], output_path: str) -> None:
        """Write VPAT data as Markdown."""
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)

        md = self._generate_markdown(vpat_data)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(md)
        logger.info(f"VPAT Markdown report written to {output_path}")

    def _generate_html(self, vpat_data: Dict[str, Any]) -> str:
        """Generate HTML content for VPAT."""
        product = vpat_data["product_info"]
        summary = vpat_data["summary"]
        conformance = vpat_data["conformance_table"]
        notes = vpat_data["notes"]
        metadata = vpat_data["metadata"]

        # Group criteria by principle for organized display
        by_principle = {"Perceivable": [], "Operable": [], "Understandable": [], "Robust": []}
        for criterion_id, data in sorted(conformance.items()):
            principle = data.get("principle", "Unknown")
            if principle in by_principle:
                by_principle[principle].append(data)

        # Build table rows
        table_rows = []
        for principle, criteria in by_principle.items():
            if criteria:
                # Principle header row
                table_rows.append(
                    f'<tr class="principle-header"><td colspan="4">'
                    f'<strong>{principle}</strong></td></tr>'
                )
                for c in criteria:
                    level_class = c["conformance_level"].replace("_", "-")
                    table_rows.append(
                        f'<tr class="{level_class}">'
                        f'<td>{c["criterion"]} {c["name"]} (Level {c["level"]})</td>'
                        f'<td class="conformance-{level_class}">{c["conformance_label"]}</td>'
                        f'<td>{c["remarks"]}</td>'
                        f'<td>{c["issue_count"]}</td>'
                        f'</tr>'
                    )

        html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VPAT - {product["name"]}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            color: #333;
        }}
        h1, h2, h3 {{
            color: #232f3e;
        }}
        .header {{
            border-bottom: 3px solid #ff9900;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }}
        .product-info {{
            background: #f5f5f5;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 30px;
        }}
        .product-info dt {{
            font-weight: bold;
            color: #232f3e;
        }}
        .product-info dd {{
            margin: 0 0 10px 0;
        }}
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin-bottom: 30px;
        }}
        .summary-card {{
            background: #fff;
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 15px;
            text-align: center;
        }}
        .summary-card.supports {{
            border-left: 4px solid #28a745;
        }}
        .summary-card.partial {{
            border-left: 4px solid #ffc107;
        }}
        .summary-card.does-not {{
            border-left: 4px solid #dc3545;
        }}
        .summary-card .number {{
            font-size: 2em;
            font-weight: bold;
            color: #232f3e;
        }}
        .summary-card .label {{
            color: #666;
            font-size: 0.9em;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 30px;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 12px;
            text-align: left;
        }}
        th {{
            background: #232f3e;
            color: white;
        }}
        .principle-header {{
            background: #f0f0f0;
        }}
        .principle-header td {{
            font-size: 1.1em;
            padding: 15px 12px;
        }}
        .conformance-supports {{
            color: #28a745;
            font-weight: bold;
        }}
        .conformance-partially-supports {{
            color: #856404;
            font-weight: bold;
        }}
        .conformance-does-not-support {{
            color: #dc3545;
            font-weight: bold;
        }}
        .supports td:first-child {{
            border-left: 3px solid #28a745;
        }}
        .partially-supports td:first-child {{
            border-left: 3px solid #ffc107;
        }}
        .does-not-support td:first-child {{
            border-left: 3px solid #dc3545;
        }}
        .notes {{
            background: #fff8e6;
            border: 1px solid #ffc107;
            border-radius: 8px;
            padding: 20px;
            margin-top: 30px;
        }}
        .notes h3 {{
            margin-top: 0;
        }}
        .footer {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
            color: #666;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Voluntary Product Accessibility Template (VPAT)</h1>
        <p>WCAG {metadata["wcag_version"]} Level {metadata["target_level"]} Conformance Report</p>
    </div>

    <div class="product-info">
        <h2>Product Information</h2>
        <dl>
            <dt>Product Name</dt>
            <dd>{product["name"]}</dd>
            <dt>Version</dt>
            <dd>{product["version"]}</dd>
            <dt>Vendor</dt>
            <dd>{product["vendor"] or "N/A"}</dd>
            <dt>Evaluation Date</dt>
            <dd>{product["date"]}</dd>
            <dt>Description</dt>
            <dd>{product["description"] or "N/A"}</dd>
        </dl>
    </div>

    <h2>Conformance Summary</h2>
    <div class="summary">
        <div class="summary-card">
            <div class="number">{summary["total_criteria"]}</div>
            <div class="label">Total Criteria</div>
        </div>
        <div class="summary-card supports">
            <div class="number">{summary["supports"]}</div>
            <div class="label">Supports</div>
        </div>
        <div class="summary-card partial">
            <div class="number">{summary["partially_supports"]}</div>
            <div class="label">Partially Supports</div>
        </div>
        <div class="summary-card does-not">
            <div class="number">{summary["does_not_support"]}</div>
            <div class="label">Does Not Support</div>
        </div>
        <div class="summary-card">
            <div class="number">{summary["conformance_percentage"]}%</div>
            <div class="label">Conformance Rate</div>
        </div>
    </div>
    <p><strong>Overall Status:</strong> {summary["overall_status"]}</p>

    <h2>WCAG 2.1 Conformance Table</h2>
    <table>
        <thead>
            <tr>
                <th>Criteria</th>
                <th>Conformance Level</th>
                <th>Remarks</th>
                <th>Issues</th>
            </tr>
        </thead>
        <tbody>
            {"".join(table_rows)}
        </tbody>
    </table>

    <div class="notes">
        <h3>Evaluation Notes</h3>
        <p><strong>Evaluation Methods:</strong> {notes["evaluation_methods"]}</p>
        <p><strong>Assistive Technology:</strong> {notes["assistive_technology"]}</p>
        <p><strong>Legal Disclaimer:</strong> {notes["legal_disclaimer"]}</p>
    </div>

    <div class="footer">
        <p>Generated by Content Accessibility Utility on AWS</p>
        <p>VPAT Version {metadata["vpat_version"]} | Generated on {metadata["evaluation_date"]}</p>
    </div>
</body>
</html>'''
        return html

    def _generate_markdown(self, vpat_data: Dict[str, Any]) -> str:
        """Generate Markdown content for VPAT."""
        product = vpat_data["product_info"]
        summary = vpat_data["summary"]
        conformance = vpat_data["conformance_table"]
        notes = vpat_data["notes"]
        metadata = vpat_data["metadata"]

        md_lines = [
            f"# Voluntary Product Accessibility Template (VPAT)",
            f"",
            f"**WCAG {metadata['wcag_version']} Level {metadata['target_level']} Conformance Report**",
            f"",
            f"## Product Information",
            f"",
            f"| Field | Value |",
            f"|-------|-------|",
            f"| Product Name | {product['name']} |",
            f"| Version | {product['version']} |",
            f"| Vendor | {product['vendor'] or 'N/A'} |",
            f"| Evaluation Date | {product['date']} |",
            f"| Description | {product['description'] or 'N/A'} |",
            f"",
            f"## Conformance Summary",
            f"",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Total Criteria | {summary['total_criteria']} |",
            f"| Supports | {summary['supports']} |",
            f"| Partially Supports | {summary['partially_supports']} |",
            f"| Does Not Support | {summary['does_not_support']} |",
            f"| Not Applicable | {summary['not_applicable']} |",
            f"| Conformance Rate | {summary['conformance_percentage']}% |",
            f"| **Overall Status** | **{summary['overall_status']}** |",
            f"",
            f"## WCAG 2.1 Conformance Table",
            f"",
            f"| Criteria | Level | Conformance | Remarks | Issues |",
            f"|----------|-------|-------------|---------|--------|",
        ]

        # Add criteria rows
        for criterion_id in sorted(conformance.keys()):
            c = conformance[criterion_id]
            md_lines.append(
                f"| {c['criterion']} {c['name']} | {c['level']} | "
                f"{c['conformance_label']} | {c['remarks']} | {c['issue_count']} |"
            )

        md_lines.extend([
            f"",
            f"## Evaluation Notes",
            f"",
            f"**Evaluation Methods:** {notes['evaluation_methods']}",
            f"",
            f"**Assistive Technology:** {notes['assistive_technology']}",
            f"",
            f"**Legal Disclaimer:** {notes['legal_disclaimer']}",
            f"",
            f"---",
            f"",
            f"*Generated by Content Accessibility Utility on AWS*",
            f"",
            f"*VPAT Version {metadata['vpat_version']} | Generated on {metadata['evaluation_date']}*",
        ])

        return "\n".join(md_lines)


def generate_vpat(
    audit_report: Dict[str, Any],
    output_path: Optional[str] = None,
    output_format: str = "html",
    product_info: Optional[Dict[str, str]] = None,
    target_level: str = "AA",
) -> Dict[str, Any]:
    """
    Generate a VPAT report from an audit report.

    This is a convenience function that creates a VPATGenerator and generates
    the report in a single call.

    Args:
        audit_report: The accessibility audit report
        output_path: Path to save the report (optional)
        output_format: Output format (html, json, or markdown)
        product_info: Dictionary containing product information
        target_level: Target WCAG conformance level (A, AA, or AAA)

    Returns:
        Dictionary containing the VPAT data
    """
    generator = VPATGenerator(product_info=product_info, target_level=target_level)
    return generator.generate(audit_report, output_path, output_format)
