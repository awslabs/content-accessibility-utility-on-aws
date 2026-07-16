# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
API for HTML accessibility auditing.

This module provides the implementation for auditing HTML documents for accessibility issues.
"""

import os
import traceback
from typing import Dict, Any, Optional

from content_accessibility_utility_on_aws.audit.auditor import AccessibilityAuditor

# IMPORTANT FIX: Import from the correct module path
from content_accessibility_utility_on_aws.audit.report_generator import generate_report
from content_accessibility_utility_on_aws.utils.logging_helper import setup_logger

# Set up module-level logger
logger = setup_logger(__name__)


def audit_html_accessibility(
    html_path: str,
    image_dir: Optional[str] = None,
    options: Optional[Dict[str, Any]] = None,
    output_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Audit an HTML document for accessibility issues.

    Args:
        html_path: Path to the HTML file or directory of HTML files.
        image_dir: Directory containing images referenced in the HTML.
        options: Audit options.
        output_path: Path to save the audit report.

    Returns:
        Dictionary containing audit results.
    """
    if options is None:
        options = {}

    try:
        # Use the AccessibilityAuditor to perform the audit
        auditor = AccessibilityAuditor(
            html_path=html_path, image_dir=image_dir, options=options
        )
        audit_results = auditor.audit()

        # Optional rendered layer: when the caller opts in (and the optional
        # browser dependency is available), render each page in a real browser
        # and append the computed/interactive issues the static pass cannot
        # detect. This is purely additive — same issue-dict shape — so the rest
        # of the pipeline is unchanged. Failures degrade to static-only.
        if options.get("rendered") or options.get("agent"):
            audit_results = _augment_with_rendered_issues(auditor, audit_results, options)

        # Log initial audit results
        logger.debug("Raw audit results type: %s", type(audit_results))
        logger.debug(
            "Raw audit results keys: %s",
            (
                list(audit_results.keys())
                if isinstance(audit_results, dict)
                else "Not a dict"
            ),
        )

        # Validate audit results structure
        if not isinstance(audit_results, dict):
            raise ValueError(f"Invalid audit results type: {type(audit_results)}")
        if "issues" not in audit_results:
            raise ValueError("Audit results missing 'issues' field")
        if not isinstance(audit_results["issues"], list):
            raise ValueError("Audit results 'issues' must be a list")

        # Log audit results details
        logger.debug("Number of issues: %d", len(audit_results["issues"]))
        logger.debug("Summary data: %s", audit_results.get("summary", {}))

        logger.debug("Generating text report...")
        text_report = generate_report(
            audit_results, output_path=output_path, report_format="text"
        )
        if text_report is None:
            logger.warning("Text report generation failed, using basic format")
            # Generate a basic text report
            total = audit_results.get("summary", {}).get("total_issues", 0)
            compliant = audit_results.get("summary", {}).get("compliant", 0)
            needs_remediation = audit_results.get("summary", {}).get(
                "needs_remediation", 0
            )
            text_report = (
                f"Total issues: {total}\nCompliant: {compliant}\nNeeds "
                + f"remediation: {needs_remediation}"
            )
        audit_results["report"] = text_report

        # Generate and save report if output path is specified
        if output_path:
            # Determine the report format
            report_format = options.get("report_format", "json")
            logger.debug(
                "Preparing to save %s report to: %s", report_format.upper(), output_path
            )

            # Create output directory if needed
            output_dir = os.path.dirname(os.path.abspath(output_path))
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
                logger.debug("Created output directory: %s", output_dir)

            # Generate report using the specified format
            logger.debug("Generating %s report...", report_format.upper())
            report_result = generate_report(
                audit_results, output_path=output_path, report_format=report_format
            )

            if report_format == "json" and report_result:
                # Only validate if it's a json report that returns data
                logger.debug(
                    "JSON report keys: %s",
                    (
                        list(report_result.keys())
                        if isinstance(report_result, dict)
                        else "Not a dict"
                    ),
                )
                if isinstance(report_result, dict) and "issues" in report_result:
                    logger.debug(
                        "Number of issues in JSON report: %d",
                        len(report_result["issues"]),
                    )

            audit_results["report_path"] = output_path
            logger.debug(
                "Successfully saved %s report to: %s",
                report_format.upper(),
                output_path,
            )

    except Exception as e:
        logger.warning("Error in report generation: %s", str(e))
        logger.warning("Error details: %s", traceback.format_exc())
        raise ValueError(f"Failed to generate report: {str(e)}") from e

    return audit_results


def _iter_page_html(auditor: "AccessibilityAuditor"):
    """Yield ``(page_number, file_path, file_name, html)`` for each page.

    Mirrors the auditor's own single-page vs. multi-page handling so the
    rendered pass sees exactly the same HTML — and the same page/file
    identity — the static pass did. ``page_number`` is None when it cannot be
    derived, matching how the static auditor leaves it unset for a lone file
    that is not named ``page-N.html``.
    """
    import re

    if getattr(auditor, "html_files", None):
        for html_file in auditor.html_files:
            try:
                with open(html_file, "r", encoding="utf-8") as f:
                    html = f.read()
            except OSError:
                continue
            file_name = os.path.basename(html_file)
            match = re.search(r"page[_-]?(\d+)\.html$", file_name, re.IGNORECASE)
            page_num = int(match.group(1)) if match else None
            yield page_num, html_file, file_name, html
    elif auditor.html_content:
        # Single-page mode. Match the static auditor, which passes the file path
        # (if any) and leaves the page number unset.
        file_path = getattr(auditor, "html_path", None)
        file_name = os.path.basename(file_path) if file_path else None
        yield None, file_path, file_name, auditor.html_content


def _augment_with_rendered_issues(
    auditor: "AccessibilityAuditor",
    audit_results: Dict[str, Any],
    options: Dict[str, Any],
) -> Dict[str, Any]:
    """Render each page, append rendered issues, and de-dup superseded ones.

    Kept import-local so the core package never hard-depends on the optional
    browser/agent stack. Any failure (missing dependency, browser launch
    failure) logs and returns the static results unchanged.
    """
    try:
        from content_accessibility_utility_on_aws.agent.browser_probe import (
            make_browser_probe,
        )
        from content_accessibility_utility_on_aws.agent.rendered_auditor import (
            RenderedAuditor,
        )
    except ImportError as e:
        logger.warning(
            "Rendered audit requested but agent layer unavailable (%s); "
            "install the optional extra: pip install "
            "content-accessibility-utility-on-aws[rendered]. Using static only.",
            e,
        )
        return audit_results

    static_issues = audit_results.get("issues", [])

    rendered_issues: list = []
    try:
        # The probe backend (local Chromium vs. managed AgentCore browser) is
        # selected by options/env, so the hosted deployment is a config swap.
        with make_browser_probe(options) as probe:
            rauditor = RenderedAuditor(probe)
            for page_num, file_path, file_name, html in _iter_page_html(auditor):
                page_issues = rauditor.audit_html(
                    html, page_number=page_num if page_num is not None else 0
                )
                # Stamp the same file/page identity the static auditor records
                # (see auditor._audit_page) so rendered issues are matched to
                # their source file during multi-page remediation and appear
                # with a file path in reports.
                for issue in page_issues:
                    _stamp_issue_location(issue, page_num, file_path, file_name)
                rendered_issues.extend(page_issues)
    except Exception as e:  # BrowserUnavailableError or anything unexpected
        logger.warning("Rendered audit failed (%s); using static results only.", e)
        return audit_results

    if not rendered_issues:
        return audit_results

    # Give rendered issues ids that do not collide with the static ids
    # (``issue-N``) or with each other across pages — downstream report/HTML
    # de-dup is keyed on id, so per-page-repeated ids would silently drop issues.
    for offset, issue in enumerate(rendered_issues, start=len(static_issues) + 1):
        issue["id"] = f"issue-{offset}"

    kept_static = RenderedAuditor.dedupe(static_issues, rendered_issues)
    combined = kept_static + rendered_issues

    logger.debug(
        "Rendered audit added %d issue(s); dropped %d superseded static issue(s).",
        len(rendered_issues),
        len(static_issues) - len(kept_static),
    )

    # Rebuild the aggregate views so summary/by_status/by_page stay consistent.
    return _rebuild_audit_results(combined)


def _stamp_issue_location(issue, page_num, file_path, file_name):
    """Record file/page identity on a rendered issue like the static auditor does.

    Mirrors ``AccessibilityAuditor._audit_page``: stores file path and name both
    under ``location`` and at the root level (for the compatibility both the
    report generators and the multi-page remediation matcher rely on), and sets
    the page number only when known.
    """
    location = issue.setdefault("location", {})
    if file_path:
        location["file_path"] = file_path
        issue["file_path"] = file_path
        location["file_name"] = file_name
        issue["file_name"] = file_name
    if page_num is not None:
        location["page_number"] = page_num
        issue["page_number"] = page_num
        location["description"] = (
            f"File: {file_name} (Page {page_num})" if file_name else f"Page {page_num}"
        )
    elif file_name:
        location["description"] = f"File: {file_name}"


def _rebuild_audit_results(issues: list) -> Dict[str, Any]:
    """Recompute the report aggregates from a combined issue list.

    Produces the same top-level structure ``AccessibilityAuditor.audit`` returns
    (summary, by_page, by_status, issues) so downstream report generation is
    unaffected.
    """
    for issue in issues:
        if "location" not in issue or issue["location"] is None:
            issue["location"] = {}
        issue["location"].setdefault("page_number", issue.get("page_number", 0))

    issues_by_status = {
        "needs_remediation": [],
        "remediated": [],
        "auto_remediated": [],
        "compliant": [],
    }
    for issue in issues:
        status = issue.get("remediation_status", "needs_remediation")
        issues_by_status.setdefault(status, []).append(issue)

    issues_by_page: Dict[Any, list] = {}
    for issue in issues:
        page = issue["location"].get("page_number", 0)
        issues_by_page.setdefault(page, []).append(issue)

    severity_counts = {"critical": 0, "major": 0, "minor": 0, "info": 0}
    for issue in issues:
        sev = issue.get("severity", "info")
        if sev in severity_counts:
            severity_counts[sev] += 1

    def _count(page_issues, status):
        return len([i for i in page_issues if i.get("remediation_status") == status])

    return {
        "summary": {
            "total_issues": len(issues),
            "needs_remediation": len(issues_by_status["needs_remediation"]),
            "remediated": len(issues_by_status["remediated"]),
            "auto_remediated": len(issues_by_status["auto_remediated"]),
            "compliant": len(issues_by_status["compliant"]),
            "severity_counts": severity_counts,
        },
        "by_page": {
            page: {
                "total": len(page_issues),
                "needs_remediation": _count(page_issues, "needs_remediation"),
                "remediated": _count(page_issues, "remediated"),
                "auto_remediated": _count(page_issues, "auto_remediated"),
                "compliant": _count(page_issues, "compliant"),
                "issues": page_issues,
            }
            for page, page_issues in issues_by_page.items()
        },
        "by_status": issues_by_status,
        "issues": issues,
    }
