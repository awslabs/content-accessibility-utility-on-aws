# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
ACR (Accessibility Conformance Report) Generator.

This module generates Accessibility Conformance Reports based on audit results.
ACR is a detailed report format that provides comprehensive accessibility
compliance information, often used for procurement and regulatory compliance.
"""

import html
import json
import os
from datetime import datetime
from typing import Dict, List, Any, Optional

from content_accessibility_utility_on_aws.audit.standards import (
    get_criteria_for_level,
)
from content_accessibility_utility_on_aws.report.scoring import (
    calculate_accessibility_score,
    calculate_wcag_compliance,
)
from content_accessibility_utility_on_aws.utils.logging_helper import setup_logger

logger = setup_logger(__name__)


# ACR Conformance Status values
ACR_STATUS = {
    "conforms": "Conforms",
    "partial": "Partially Conforms",
    "does_not_conform": "Does Not Conform",
    "not_applicable": "Not Applicable",
    "not_evaluated": "Not Evaluated",
}

# Issue severity to ACR status mapping
SEVERITY_TO_STATUS = {
    "critical": "does_not_conform",
    "major": "partial",
    "minor": "partial",
    "info": "conforms",
}


class ACRGenerator:
    """
    Generator for Accessibility Conformance Reports (ACR).

    ACR provides a comprehensive view of accessibility compliance status,
    including detailed findings, remediation guidance, and executive summary.
    """

    def __init__(
        self,
        organization_info: Optional[Dict[str, str]] = None,
        target_level: str = "AA",
        include_remediation_guidance: bool = True,
    ):
        """
        Initialize the ACR generator.

        Args:
            organization_info: Dictionary containing organization/product information
            target_level: Target WCAG conformance level (A, AA, or AAA)
            include_remediation_guidance: Whether to include remediation suggestions
        """
        self.organization_info = organization_info or {}
        self.target_level = target_level.upper()
        self.include_remediation_guidance = include_remediation_guidance
        self.criteria = get_criteria_for_level(self.target_level)

    def generate(
        self,
        audit_report: Dict[str, Any],
        output_path: Optional[str] = None,
        output_format: str = "html",
    ) -> Dict[str, Any]:
        """
        Generate an ACR from an audit report.

        Args:
            audit_report: The accessibility audit report
            output_path: Path to save the report (optional)
            output_format: Output format (html, json, or markdown)

        Returns:
            Dictionary containing the ACR data
        """
        logger.info(f"Generating ACR for WCAG {self.target_level}")

        # Calculate score and compliance
        score_data = calculate_accessibility_score(
            audit_report.get("issues", []),
            target_level=self.target_level
        )
        compliance_data = calculate_wcag_compliance(
            audit_report.get("issues", []), self.target_level
        )

        # Build detailed findings
        findings = self._build_findings(audit_report)

        # Build executive summary
        executive_summary = self._build_executive_summary(
            score_data, compliance_data, findings
        )

        # Build recommendations
        recommendations = self._build_recommendations(findings)

        # Create the ACR structure
        acr_data = {
            "metadata": {
                "report_type": "Accessibility Conformance Report",
                "wcag_version": "2.1",
                "target_level": self.target_level,
                "evaluation_date": datetime.now().isoformat(),
                "report_date": datetime.now().strftime("%B %d, %Y"),
                "generator": "Content Accessibility Utility on AWS",
            },
            "organization_info": self._get_organization_info(),
            "executive_summary": executive_summary,
            "score": score_data,
            "compliance": compliance_data,
            "findings_by_principle": findings,
            "findings_summary": self._summarize_findings(findings),
            "recommendations": recommendations,
            "methodology": self._get_methodology(),
            "appendix": self._build_appendix(audit_report),
        }

        # Write output if path provided
        if output_path:
            if output_format == "html":
                self._write_html(acr_data, output_path)
            elif output_format == "json":
                self._write_json(acr_data, output_path)
            elif output_format == "markdown":
                self._write_markdown(acr_data, output_path)
            else:
                logger.warning(f"Unknown format {output_format}, using HTML")
                self._write_html(acr_data, output_path)

        return acr_data

    def _get_organization_info(self) -> Dict[str, str]:
        """Get organization information with defaults."""
        return {
            "name": self.organization_info.get("name") or "Organization Name",
            "product": self.organization_info.get("product") or "Product/Website Name",
            "url": self.organization_info.get("url") or "",
            "evaluator": self.organization_info.get("evaluator") or "Content Accessibility Utility on AWS",
            "contact": self.organization_info.get("contact") or "",
            "scope": self.organization_info.get("scope") or "Full accessibility audit of content",
        }

    def _build_findings(self, audit_report: Dict[str, Any]) -> Dict[str, List[Dict]]:
        """
        Build findings organized by WCAG principle.

        Args:
            audit_report: The accessibility audit report

        Returns:
            Dictionary mapping principles to findings
        """
        findings = {
            "Perceivable": [],
            "Operable": [],
            "Understandable": [],
            "Robust": [],
        }

        # Group issues by WCAG criterion
        issues_by_criterion = {}
        for issue in audit_report.get("issues", []):
            criterion = issue.get("wcag_criterion", "unknown")
            if criterion not in issues_by_criterion:
                issues_by_criterion[criterion] = []
            issues_by_criterion[criterion].append(issue)

        # Process each criterion
        for criterion_id, criterion_info in self.criteria.items():
            principle = criterion_info.get("principle", "Unknown")
            issues = issues_by_criterion.get(criterion_id, [])

            # Determine status
            status = self._determine_status(issues)

            # Build finding entry
            finding = {
                "criterion_id": criterion_id,
                "criterion_name": criterion_info["name"],
                "level": criterion_info["level"],
                "guideline": criterion_info["guideline"],
                "description": criterion_info["description"],
                "status": status,
                "status_label": ACR_STATUS.get(status, "Not Evaluated"),
                "issue_count": len(issues),
                "issues": [
                    {
                        "type": i.get("type", "unknown"),
                        "severity": i.get("severity", "minor"),
                        "message": i.get("message", ""),
                        "element": i.get("selector", i.get("element", "")),
                        "remediation_status": i.get("remediation_status", "needs_remediation"),
                    }
                    for i in issues
                ],
            }

            # Add remediation guidance if enabled
            if self.include_remediation_guidance and issues:
                finding["remediation_guidance"] = self._get_remediation_guidance(
                    criterion_id, issues
                )

            if principle in findings:
                findings[principle].append(finding)

        return findings

    def _determine_status(self, issues: List[Dict[str, Any]]) -> str:
        """Determine conformance status based on issues."""
        if not issues:
            return "conforms"

        # Check if all issues are remediated
        unremediated = [
            i for i in issues
            if i.get("remediation_status", "needs_remediation") != "remediated"
        ]

        if not unremediated:
            return "conforms"

        # Check severities
        has_critical = any(i.get("severity") == "critical" for i in unremediated)
        major_count = sum(1 for i in unremediated if i.get("severity") == "major")

        if has_critical or major_count > 2:
            return "does_not_conform"
        else:
            # Has unremediated issues but not critical/many major - partial conformance
            return "partial"

    def _get_remediation_guidance(
        self, criterion_id: str, issues: List[Dict[str, Any]]
    ) -> str:
        """Get remediation guidance for a criterion."""
        # General guidance based on criterion type
        guidance_map = {
            "1.1.1": "Provide text alternatives for all non-text content. Add alt text to images, labels to form controls, and descriptions for complex graphics.",
            "1.3.1": "Ensure information and relationships conveyed through presentation are programmatically determinable. Use semantic HTML elements and ARIA attributes appropriately.",
            "1.4.3": "Ensure text has sufficient contrast against its background. Minimum ratio is 4.5:1 for normal text and 3:1 for large text.",
            "1.4.11": "Ensure UI components and graphical objects have sufficient contrast (at least 3:1).",
            "2.1.1": "Ensure all functionality is available using keyboard alone. Add keyboard handlers and ensure focus management.",
            "2.4.1": "Provide a way to bypass repeated blocks of content. Add skip links and proper heading structure.",
            "2.4.4": "Ensure link purpose can be determined from link text alone or with context. Avoid generic link text like 'click here'.",
            "2.4.6": "Ensure headings and labels describe their topic or purpose clearly and accurately.",
            "3.1.1": "Set the language of the page using the lang attribute on the html element.",
            "3.3.2": "Provide labels or instructions for form inputs. Use label elements or aria-label/aria-labelledby.",
            "4.1.1": "Ensure HTML is well-formed with complete start and end tags, proper nesting, and unique IDs.",
            "4.1.2": "Ensure all UI components have accessible names and roles. Use semantic HTML or ARIA attributes.",
        }

        base_guidance = guidance_map.get(
            criterion_id,
            f"Review and address the {len(issues)} issue(s) found for this criterion."
        )

        # Add specific issue types found
        issue_types = set(i.get("type", "unknown") for i in issues)
        if issue_types:
            type_list = ", ".join(sorted(issue_types))
            base_guidance += f" Issue types found: {type_list}."

        return base_guidance

    def _build_executive_summary(
        self,
        score_data: Dict[str, Any],
        compliance_data: Dict[str, Any],
        findings: Dict[str, List[Dict]],
    ) -> Dict[str, Any]:
        """Build executive summary section."""
        # Count findings by status
        total_criteria = sum(len(f) for f in findings.values())
        conforming = sum(
            1 for principle_findings in findings.values()
            for f in principle_findings if f["status"] == "conforms"
        )
        partial = sum(
            1 for principle_findings in findings.values()
            for f in principle_findings if f["status"] == "partial"
        )
        non_conforming = sum(
            1 for principle_findings in findings.values()
            for f in principle_findings if f["status"] == "does_not_conform"
        )

        # Determine overall status
        if non_conforming > 0:
            overall_status = "Does Not Conform"
            overall_description = (
                f"The evaluated content does not conform to WCAG 2.1 Level {self.target_level}. "
                f"There are {non_conforming} criterion/criteria with critical non-conformance issues "
                "that require immediate attention."
            )
        elif partial > 0:
            overall_status = "Partially Conforms"
            overall_description = (
                f"The evaluated content partially conforms to WCAG 2.1 Level {self.target_level}. "
                f"There are {partial} criterion/criteria with issues that should be addressed "
                "to achieve full conformance."
            )
        else:
            overall_status = "Conforms"
            overall_description = (
                f"The evaluated content conforms to WCAG 2.1 Level {self.target_level}. "
                "No significant accessibility barriers were identified during the evaluation."
            )

        return {
            "overall_status": overall_status,
            "overall_description": overall_description,
            "total_criteria_evaluated": total_criteria,
            "conforming_criteria": conforming,
            "partial_conformance": partial,
            "non_conforming_criteria": non_conforming,
            "critical_issues": score_data["details"]["critical_issues"],
            "major_issues": score_data["details"]["major_issues"],
            "minor_issues": score_data["details"]["minor_issues"],
            "key_findings": self._get_key_findings(findings),
            # Standard VPAT conformance summary
            "conformance_summary": score_data.get("summary", {}),
        }

    def _get_key_findings(self, findings: Dict[str, List[Dict]]) -> List[str]:
        """Extract key findings for executive summary."""
        key_findings = []

        # Identify non-conforming criteria
        for principle, principle_findings in findings.items():
            for f in principle_findings:
                if f["status"] == "does_not_conform":
                    key_findings.append(
                        f"Critical: {f['criterion_id']} {f['criterion_name']} - "
                        f"{f['issue_count']} issue(s) requiring immediate attention."
                    )

        # If no critical issues, mention partial conformance
        if not key_findings:
            for principle, principle_findings in findings.items():
                for f in principle_findings:
                    if f["status"] == "partial" and len(key_findings) < 5:
                        key_findings.append(
                            f"{f['criterion_id']} {f['criterion_name']} - "
                            f"{f['issue_count']} issue(s) to address."
                        )

        # If still no findings, indicate good conformance
        if not key_findings:
            key_findings.append(
                "No significant accessibility issues identified. Content demonstrates "
                "good accessibility practices."
            )

        return key_findings[:10]  # Limit to top 10 findings

    def _summarize_findings(
        self, findings: Dict[str, List[Dict]]
    ) -> Dict[str, Dict[str, int]]:
        """Summarize findings by principle."""
        summary = {}
        for principle, principle_findings in findings.items():
            summary[principle] = {
                "total": len(principle_findings),
                "conforms": sum(1 for f in principle_findings if f["status"] == "conforms"),
                "partial": sum(1 for f in principle_findings if f["status"] == "partial"),
                "does_not_conform": sum(
                    1 for f in principle_findings if f["status"] == "does_not_conform"
                ),
                "issues": sum(f["issue_count"] for f in principle_findings),
            }
        return summary

    def _build_recommendations(
        self, findings: Dict[str, List[Dict]]
    ) -> List[Dict[str, Any]]:
        """Build prioritized recommendations."""
        recommendations = []
        priority = 1

        # First, critical issues (does_not_conform)
        for principle, principle_findings in findings.items():
            for f in principle_findings:
                if f["status"] == "does_not_conform":
                    recommendations.append({
                        "priority": priority,
                        "urgency": "Critical",
                        "criterion": f"{f['criterion_id']} {f['criterion_name']}",
                        "description": f.get(
                            "remediation_guidance",
                            f"Address {f['issue_count']} critical accessibility issues."
                        ),
                        "impact": "High - Affects ability of users with disabilities to access content",
                    })
                    priority += 1

        # Then, partial conformance issues
        for principle, principle_findings in findings.items():
            for f in principle_findings:
                if f["status"] == "partial":
                    recommendations.append({
                        "priority": priority,
                        "urgency": "Important",
                        "criterion": f"{f['criterion_id']} {f['criterion_name']}",
                        "description": f.get(
                            "remediation_guidance",
                            f"Address {f['issue_count']} accessibility issues."
                        ),
                        "impact": "Medium - May impact some users with disabilities",
                    })
                    priority += 1

        return recommendations

    def _get_methodology(self) -> Dict[str, str]:
        """Get methodology section content."""
        return {
            "evaluation_method": (
                "This evaluation was conducted using automated accessibility testing tools "
                "provided by the Content Accessibility Utility on AWS. The tool analyzes "
                "HTML content against WCAG 2.1 success criteria and identifies potential "
                "accessibility barriers."
            ),
            "scope": (
                f"The evaluation covers WCAG 2.1 Level {self.target_level} conformance. "
                "This includes all Level A criteria and, for AA conformance, all Level AA "
                "criteria as well."
            ),
            "limitations": (
                "Automated testing can identify many accessibility issues but cannot detect "
                "all barriers. Manual testing with assistive technologies and user testing "
                "with people with disabilities is recommended for comprehensive evaluation."
            ),
            "wcag_reference": (
                "Web Content Accessibility Guidelines (WCAG) 2.1 - "
                "https://www.w3.org/TR/WCAG21/"
            ),
        }

    def _build_appendix(self, audit_report: Dict[str, Any]) -> Dict[str, Any]:
        """Build appendix with additional details."""
        issues = audit_report.get("issues", [])

        # Group by severity
        by_severity = {"critical": [], "major": [], "minor": [], "info": []}
        for issue in issues:
            severity = issue.get("severity", "minor")
            if severity in by_severity:
                by_severity[severity].append({
                    "type": issue.get("type", "unknown"),
                    "message": issue.get("message", ""),
                    "wcag_criterion": issue.get("wcag_criterion", ""),
                    "element": issue.get("selector", issue.get("element", ""))[:200],
                })

        # Group by type
        by_type = {}
        for issue in issues:
            issue_type = issue.get("type", "unknown")
            if issue_type not in by_type:
                by_type[issue_type] = 0
            by_type[issue_type] += 1

        return {
            "issues_by_severity": {k: len(v) for k, v in by_severity.items()},
            "issues_by_type": by_type,
            "detailed_issues": {
                "critical": by_severity["critical"][:20],  # Limit detail
                "major": by_severity["major"][:20],
            },
            "glossary": {
                "WCAG": "Web Content Accessibility Guidelines",
                "Level A": "Minimum level of conformance",
                "Level AA": "Enhanced level of conformance (most common target)",
                "Level AAA": "Highest level of conformance",
                "ACR": "Accessibility Conformance Report",
                "VPAT": "Voluntary Product Accessibility Template",
            },
        }

    def _write_html(self, acr_data: Dict[str, Any], output_path: str) -> None:
        """Write ACR data as HTML."""
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)

        html = self._generate_html(acr_data)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)
        logger.info(f"ACR HTML report written to {output_path}")

    def _write_json(self, acr_data: Dict[str, Any], output_path: str) -> None:
        """Write ACR data as JSON."""
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(acr_data, f, indent=2)
        logger.info(f"ACR JSON report written to {output_path}")

    def _write_markdown(self, acr_data: Dict[str, Any], output_path: str) -> None:
        """Write ACR data as Markdown."""
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)

        md = self._generate_markdown(acr_data)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(md)
        logger.info(f"ACR Markdown report written to {output_path}")

    def _generate_html(self, acr_data: Dict[str, Any]) -> str:
        """Generate HTML content for ACR."""
        org = acr_data["organization_info"]
        summary = acr_data["executive_summary"]
        findings = acr_data["findings_by_principle"]
        findings_summary = acr_data["findings_summary"]
        recommendations = acr_data["recommendations"]
        methodology = acr_data["methodology"]
        metadata = acr_data["metadata"]

        # Build findings tables
        findings_html = []
        for principle in ["Perceivable", "Operable", "Understandable", "Robust"]:
            principle_findings = findings.get(principle, [])
            if principle_findings:
                ps = findings_summary.get(principle, {})
                findings_html.append(f'''
                <div class="principle-section">
                    <h3>{principle}</h3>
                    <p class="principle-summary">
                        {ps.get("total", 0)} criteria evaluated |
                        {ps.get("conforms", 0)} conforming |
                        {ps.get("partial", 0)} partial |
                        {ps.get("does_not_conform", 0)} non-conforming |
                        {ps.get("issues", 0)} total issues
                    </p>
                    <table class="findings-table">
                        <thead>
                            <tr>
                                <th>Criterion</th>
                                <th>Status</th>
                                <th>Issues</th>
                                <th>Details</th>
                            </tr>
                        </thead>
                        <tbody>
                ''')
                for f in principle_findings:
                    status = f.get("status") or "not_evaluated"
                    status_class = status.replace("_", "-")
                    findings_html.append(f'''
                            <tr class="{status_class}">
                                <td>
                                    <strong>{f["criterion_id"]}</strong><br>
                                    {f["criterion_name"]}<br>
                                    <small>Level {f["level"]}</small>
                                </td>
                                <td class="status-{status_class}">{f["status_label"]}</td>
                                <td>{f["issue_count"]}</td>
                                <td>
                                    <small>{f.get("remediation_guidance", f["description"][:150])}</small>
                                </td>
                            </tr>
                    ''')
                findings_html.append('</tbody></table></div>')

        # Build recommendations list
        recommendations_html = []
        for rec in recommendations[:10]:
            urgency_class = rec["urgency"].lower()
            recommendations_html.append(f'''
                <div class="recommendation {urgency_class}">
                    <span class="priority">#{rec["priority"]}</span>
                    <span class="urgency {urgency_class}">{rec["urgency"]}</span>
                    <strong>{rec["criterion"]}</strong>
                    <p>{rec["description"]}</p>
                    <small>Impact: {rec["impact"]}</small>
                </div>
            ''')

        # Build key findings list
        key_findings_html = "\n".join(
            f"<li>{html.escape(finding)}</li>" for finding in summary["key_findings"]
        )

        html_content = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Accessibility Conformance Report - {html.escape(org["product"])}</title>
    <style>
        * {{
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            color: #333;
            background: #f9f9f9;
        }}
        .report-container {{
            background: white;
            padding: 40px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #232f3e;
            border-bottom: 3px solid #ff9900;
            padding-bottom: 15px;
        }}
        h2 {{
            color: #232f3e;
            margin-top: 40px;
            border-bottom: 1px solid #ddd;
            padding-bottom: 10px;
        }}
        h3 {{
            color: #545b64;
        }}
        .metadata {{
            background: #f5f5f5;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 30px;
        }}
        .executive-summary {{
            background: linear-gradient(135deg, #232f3e 0%, #37475a 100%);
            color: white;
            padding: 30px;
            border-radius: 8px;
            margin-bottom: 30px;
        }}
        .executive-summary h2 {{
            color: #ff9900;
            border: none;
            margin-top: 0;
        }}
        .status-badge {{
            display: inline-block;
            padding: 8px 20px;
            border-radius: 20px;
            font-weight: bold;
            font-size: 1.1em;
        }}
        .status-badge.conforms {{
            background: #28a745;
        }}
        .status-badge.partial {{
            background: #ffc107;
            color: #333;
        }}
        .status-badge.does-not-conform {{
            background: #dc3545;
        }}
        .score-display {{
            display: flex;
            gap: 30px;
            margin: 20px 0;
            flex-wrap: wrap;
        }}
        .score-card {{
            background: rgba(255,255,255,0.1);
            padding: 15px 25px;
            border-radius: 8px;
            text-align: center;
        }}
        .score-card .value {{
            font-size: 2em;
            font-weight: bold;
            color: #ff9900;
        }}
        .score-card .label {{
            font-size: 0.9em;
            opacity: 0.9;
        }}
        .key-findings {{
            background: rgba(255,255,255,0.1);
            padding: 15px 20px;
            border-radius: 8px;
            margin-top: 20px;
        }}
        .key-findings ul {{
            margin: 10px 0 0 0;
            padding-left: 20px;
        }}
        .principle-section {{
            margin-bottom: 30px;
            padding: 20px;
            background: #fafafa;
            border-radius: 8px;
        }}
        .principle-summary {{
            color: #666;
            font-size: 0.9em;
            margin-bottom: 15px;
        }}
        .findings-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9em;
        }}
        .findings-table th, .findings-table td {{
            border: 1px solid #ddd;
            padding: 10px;
            text-align: left;
            vertical-align: top;
        }}
        .findings-table th {{
            background: #232f3e;
            color: white;
        }}
        .findings-table tr.conforms td:first-child {{
            border-left: 4px solid #28a745;
        }}
        .findings-table tr.partial td:first-child {{
            border-left: 4px solid #ffc107;
        }}
        .findings-table tr.does-not-conform td:first-child {{
            border-left: 4px solid #dc3545;
        }}
        .status-conforms {{ color: #28a745; font-weight: bold; }}
        .status-partial {{ color: #856404; font-weight: bold; }}
        .status-does-not-conform {{ color: #dc3545; font-weight: bold; }}
        .recommendation {{
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 15px;
            background: white;
        }}
        .recommendation.critical {{
            border-left: 4px solid #dc3545;
        }}
        .recommendation.important {{
            border-left: 4px solid #ffc107;
        }}
        .recommendation .priority {{
            display: inline-block;
            background: #232f3e;
            color: white;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.85em;
            margin-right: 10px;
        }}
        .recommendation .urgency {{
            display: inline-block;
            padding: 2px 10px;
            border-radius: 4px;
            font-size: 0.85em;
            font-weight: bold;
        }}
        .urgency.critical {{
            background: #dc3545;
            color: white;
        }}
        .urgency.important {{
            background: #ffc107;
            color: #333;
        }}
        .methodology {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            margin-top: 30px;
        }}
        .methodology p {{
            margin: 10px 0;
        }}
        .footer {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
            color: #666;
            font-size: 0.9em;
            text-align: center;
        }}
        @media print {{
            body {{
                background: white;
            }}
            .report-container {{
                box-shadow: none;
            }}
            .executive-summary {{
                -webkit-print-color-adjust: exact;
                print-color-adjust: exact;
            }}
        }}
    </style>
</head>
<body>
    <div class="report-container">
        <h1>Accessibility Conformance Report</h1>

        <div class="metadata">
            <strong>{html.escape(org["product"])}</strong> | {html.escape(org["name"])}<br>
            <small>
                Evaluation Date: {metadata["report_date"]} |
                WCAG Version: {metadata["wcag_version"]} |
                Target Level: {metadata["target_level"]}
            </small>
        </div>

        <div class="executive-summary">
            <h2>Executive Summary</h2>
            <div class="status-badge {(summary.get("overall_status") or "Unknown").lower().replace(" ", "-")}">
                {summary.get("overall_status", "Unknown")}
            </div>
            <p>{summary["overall_description"]}</p>

            <div class="conformance-summary">
                <h3>VPAT Conformance Summary</h3>
                <div class="score-display">
                    <div class="score-card">
                        <div class="value">{summary["conforming_criteria"]}</div>
                        <div class="label">Supports</div>
                    </div>
                    <div class="score-card">
                        <div class="value">{summary["partial_conformance"]}</div>
                        <div class="label">Partially Supports</div>
                    </div>
                    <div class="score-card">
                        <div class="value">{summary["non_conforming_criteria"]}</div>
                        <div class="label">Does Not Support</div>
                    </div>
                </div>
                <h3>Issue Summary</h3>
                <div class="score-display">
                    <div class="score-card">
                        <div class="value">{summary["critical_issues"]}</div>
                        <div class="label">Critical</div>
                    </div>
                    <div class="score-card">
                        <div class="value">{summary["major_issues"]}</div>
                        <div class="label">Major</div>
                    </div>
                    <div class="score-card">
                        <div class="value">{summary["minor_issues"]}</div>
                        <div class="label">Minor</div>
                    </div>
                </div>
            </div>

            <div class="key-findings">
                <strong>Key Findings:</strong>
                <ul>
                    {key_findings_html}
                </ul>
            </div>
        </div>

        <h2>Detailed Findings by WCAG Principle</h2>
        {"".join(findings_html)}

        <h2>Prioritized Recommendations</h2>
        {"".join(recommendations_html) if recommendations_html else "<p>No remediation actions required.</p>"}

        <div class="methodology">
            <h2>Evaluation Methodology</h2>
            <p><strong>Method:</strong> {methodology["evaluation_method"]}</p>
            <p><strong>Scope:</strong> {methodology["scope"]}</p>
            <p><strong>Limitations:</strong> {methodology["limitations"]}</p>
            <p><strong>Reference:</strong> {methodology["wcag_reference"]}</p>
        </div>

        <div class="footer">
            <p>Generated by Content Accessibility Utility on AWS</p>
            <p>{metadata["report_date"]}</p>
        </div>
    </div>
</body>
</html>'''
        return html_content

    def _generate_markdown(self, acr_data: Dict[str, Any]) -> str:
        """Generate Markdown content for ACR."""
        org = acr_data["organization_info"]
        summary = acr_data["executive_summary"]
        findings = acr_data["findings_by_principle"]
        recommendations = acr_data["recommendations"]
        methodology = acr_data["methodology"]
        metadata = acr_data["metadata"]

        md_lines = [
            f"# Accessibility Conformance Report",
            f"",
            f"**{org['product']}** | {org['name']}",
            f"",
            f"- Evaluation Date: {metadata['report_date']}",
            f"- WCAG Version: {metadata['wcag_version']}",
            f"- Target Level: {metadata['target_level']}",
            f"",
            f"---",
            f"",
            f"## Executive Summary",
            f"",
            f"**Overall Status: {summary['overall_status']}**",
            f"",
            f"{summary['overall_description']}",
            f"",
            f"### VPAT Conformance Summary",
            f"",
            f"| Conformance Level | Criteria Count |",
            f"|-------------------|----------------|",
            f"| Supports | {summary['conforming_criteria']} |",
            f"| Partially Supports | {summary['partial_conformance']} |",
            f"| Does Not Support | {summary['non_conforming_criteria']} |",
            f"",
            f"### Issue Summary",
            f"",
            f"| Severity | Count |",
            f"|----------|-------|",
            f"| Critical | {summary['critical_issues']} |",
            f"| Major | {summary['major_issues']} |",
            f"| Minor | {summary['minor_issues']} |",
            f"",
            f"### Key Findings",
            f"",
        ]

        for finding in summary["key_findings"]:
            md_lines.append(f"- {finding}")

        md_lines.extend([
            f"",
            f"---",
            f"",
            f"## Detailed Findings",
            f"",
        ])

        for principle in ["Perceivable", "Operable", "Understandable", "Robust"]:
            principle_findings = findings.get(principle, [])
            if principle_findings:
                md_lines.extend([
                    f"### {principle}",
                    f"",
                    f"| Criterion | Status | Issues | Details |",
                    f"|-----------|--------|--------|---------|",
                ])
                for f in principle_findings:
                    details = f.get("remediation_guidance", f["description"])[:100]
                    md_lines.append(
                        f"| {f['criterion_id']} {f['criterion_name']} | "
                        f"{f['status_label']} | {f['issue_count']} | {details}... |"
                    )
                md_lines.append("")

        md_lines.extend([
            f"---",
            f"",
            f"## Recommendations",
            f"",
        ])

        for rec in recommendations[:10]:
            md_lines.extend([
                f"### #{rec['priority']} [{rec['urgency']}] {rec['criterion']}",
                f"",
                f"{rec['description']}",
                f"",
                f"*Impact: {rec['impact']}*",
                f"",
            ])

        md_lines.extend([
            f"---",
            f"",
            f"## Methodology",
            f"",
            f"**Evaluation Method:** {methodology['evaluation_method']}",
            f"",
            f"**Scope:** {methodology['scope']}",
            f"",
            f"**Limitations:** {methodology['limitations']}",
            f"",
            f"**Reference:** {methodology['wcag_reference']}",
            f"",
            f"---",
            f"",
            f"*Generated by Content Accessibility Utility on AWS on {metadata['report_date']}*",
        ])

        return "\n".join(md_lines)


def generate_acr(
    audit_report: Dict[str, Any],
    output_path: Optional[str] = None,
    output_format: str = "html",
    organization_info: Optional[Dict[str, str]] = None,
    target_level: str = "AA",
    include_remediation_guidance: bool = True,
) -> Dict[str, Any]:
    """
    Generate an Accessibility Conformance Report from an audit report.

    This is a convenience function that creates an ACRGenerator and generates
    the report in a single call.

    Args:
        audit_report: The accessibility audit report
        output_path: Path to save the report (optional)
        output_format: Output format (html, json, or markdown)
        organization_info: Dictionary containing organization/product information
        target_level: Target WCAG conformance level (A, AA, or AAA)
        include_remediation_guidance: Whether to include remediation suggestions

    Returns:
        Dictionary containing the ACR data
    """
    generator = ACRGenerator(
        organization_info=organization_info,
        target_level=target_level,
        include_remediation_guidance=include_remediation_guidance,
    )
    return generator.generate(audit_report, output_path, output_format)
