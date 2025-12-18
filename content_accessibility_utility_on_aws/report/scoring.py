# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Accessibility conformance module.

This module provides functionality to calculate VPAT/ACR conformance levels
based on audit results, using standard VPAT 2.4 conformance terminology.

Standard VPAT Conformance Levels:
- Supports: The functionality fully meets the criterion
- Partially Supports: Some functionality does not meet the criterion
- Does Not Support: Most functionality does not meet the criterion
- Not Applicable: The criterion is not relevant to the product
- Not Evaluated: The product has not been evaluated against the criterion
"""

from typing import Dict, List, Any
from content_accessibility_utility_on_aws.audit.standards import (
    WCAG_LEVELS,
    get_criterion_info,
)


# Standard VPAT 2.4 Conformance Levels
CONFORMANCE_LEVELS = {
    "supports": "Supports",
    "partially_supports": "Partially Supports",
    "does_not_support": "Does Not Support",
    "not_applicable": "Not Applicable",
    "not_evaluated": "Not Evaluated",
}


def get_criterion_conformance(issues_for_criterion: List[Dict[str, Any]]) -> str:
    """
    Determine VPAT conformance level for a single criterion based on its issues.

    Uses standard VPAT 2.4 conformance terminology.

    Args:
        issues_for_criterion: List of issues for this specific criterion

    Returns:
        Standard VPAT conformance level string
    """
    if not issues_for_criterion:
        return CONFORMANCE_LEVELS["supports"]

    # Count issues by severity
    severities = [i.get("severity", "minor").lower() for i in issues_for_criterion]
    critical_count = severities.count("critical")
    major_count = severities.count("major")
    minor_count = severities.count("minor")

    # Determine conformance based on severity
    if critical_count > 0:
        return CONFORMANCE_LEVELS["does_not_support"]
    elif major_count > 0:
        return CONFORMANCE_LEVELS["does_not_support"]
    elif minor_count > 0:
        return CONFORMANCE_LEVELS["partially_supports"]
    else:
        return CONFORMANCE_LEVELS["supports"]


def calculate_conformance_summary(
    issues: List[Dict[str, Any]],
    target_level: str = "AA",
) -> Dict[str, Any]:
    """
    Calculate VPAT conformance summary for all evaluated criteria.

    This replaces the non-standard numeric scoring with standard VPAT
    conformance levels per criterion.

    Args:
        issues: List of accessibility issues from an audit
        target_level: Target WCAG level (A, AA, or AAA)

    Returns:
        Dictionary containing:
            - conformance_by_criterion: Conformance level for each criterion
            - summary: Count of criteria at each conformance level
            - issues_by_severity: Count of issues by severity
            - evaluated_criteria: List of criteria that were evaluated
    """
    # Filter out "compliant-*" entries which are positive markers
    active_issues = [
        i for i in issues
        if i.get("remediation_status", "needs_remediation") == "needs_remediation"
        and not i.get("type", "").startswith("compliant-")
    ]

    # Group issues by WCAG criterion
    issues_by_criterion: Dict[str, List[Dict[str, Any]]] = {}
    severity_counts = {"critical": 0, "major": 0, "minor": 0, "info": 0}

    for issue in active_issues:
        criterion = issue.get("wcag_criterion", "")
        severity = issue.get("severity", "minor").lower()

        if criterion and criterion != "unknown":
            if criterion not in issues_by_criterion:
                issues_by_criterion[criterion] = []
            issues_by_criterion[criterion].append(issue)

        if severity in severity_counts:
            severity_counts[severity] += 1

    # Calculate conformance for each criterion with issues
    conformance_by_criterion = {}
    for criterion, criterion_issues in issues_by_criterion.items():
        conformance_by_criterion[criterion] = {
            "conformance_level": get_criterion_conformance(criterion_issues),
            "issue_count": len(criterion_issues),
            "max_severity": max(
                [i.get("severity", "minor") for i in criterion_issues],
                key=lambda s: {"critical": 4, "major": 3, "minor": 2, "info": 1}.get(s.lower(), 0)
            ),
            "criterion_info": get_criterion_info(criterion),
        }

    # Count criteria at each conformance level
    conformance_summary = {
        "Supports": 0,
        "Partially Supports": 0,
        "Does Not Support": 0,
        "Not Applicable": 0,
        "Not Evaluated": 0,
    }

    for criterion_data in conformance_by_criterion.values():
        level = criterion_data["conformance_level"]
        if level in conformance_summary:
            conformance_summary[level] += 1

    # Criteria without issues are "Supports"
    criteria_with_issues = len(conformance_by_criterion)

    return {
        "target_level": target_level.upper(),
        "conformance_by_criterion": conformance_by_criterion,
        "summary": conformance_summary,
        "criteria_with_issues": criteria_with_issues,
        "total_issues": len(active_issues),
        "issues_by_severity": severity_counts,
        "failing_criteria": list(issues_by_criterion.keys()),
    }


# Keep this function for backwards compatibility but mark as using standard levels
def calculate_accessibility_score(
    issues: List[Dict[str, Any]],
    target_level: str = "AA",
    include_remediated: bool = False,
) -> Dict[str, Any]:
    """
    Calculate accessibility conformance summary.

    Note: This function name is kept for backwards compatibility.
    It now returns VPAT-standard conformance data instead of arbitrary scores.

    Args:
        issues: List of accessibility issues from an audit
        target_level: Target WCAG level (A, AA, or AAA)
        include_remediated: Whether to include remediated issues

    Returns:
        Dictionary containing conformance summary with standard VPAT levels
    """
    # Filter issues based on remediation status
    if include_remediated:
        filtered_issues = [
            i for i in issues
            if not i.get("type", "").startswith("compliant-")
        ]
    else:
        filtered_issues = [
            i for i in issues
            if i.get("remediation_status", "needs_remediation") == "needs_remediation"
            and not i.get("type", "").startswith("compliant-")
        ]

    conformance = calculate_conformance_summary(filtered_issues, target_level)

    # Add fields expected by existing code (for backwards compatibility)
    return {
        # Standard conformance data
        "conformance_by_criterion": conformance["conformance_by_criterion"],
        "summary": conformance["summary"],
        "target_level": target_level.upper(),

        # Issue counts (factual, not made-up scores)
        "total_issues": conformance["total_issues"],
        "criteria_with_issues": conformance["criteria_with_issues"],
        "issues_by_severity": conformance["issues_by_severity"],
        "failing_criteria": conformance["failing_criteria"],

        # Backwards compatibility fields (deprecated)
        "issues_counted": conformance["total_issues"],
        "breakdown": {
            "by_severity": conformance["issues_by_severity"],
        },
        "details": {
            "critical_issues": conformance["issues_by_severity"]["critical"],
            "major_issues": conformance["issues_by_severity"]["major"],
            "minor_issues": conformance["issues_by_severity"]["minor"],
            "info_issues": conformance["issues_by_severity"]["info"],
        },
    }


def calculate_wcag_compliance(
    issues: List[Dict[str, Any]],
    target_level: str = "AA",
) -> Dict[str, Any]:
    """
    Calculate WCAG compliance status for a specific conformance level.

    WCAG compliance requires ALL criteria at or below the target level
    to have no critical or major issues.

    Args:
        issues: List of accessibility issues from an audit
        target_level: Target WCAG level ("A", "AA", or "AAA")

    Returns:
        Dictionary containing:
            - compliant: Boolean indicating full compliance
            - target_level: The target level checked
            - criteria_with_issues: Number of criteria with issues
            - issues_by_criterion: Issues grouped by WCAG criterion
    """
    # Only consider issues needing remediation, excluding "compliant-*" entries
    active_issues = [
        i for i in issues
        if i.get("remediation_status", "needs_remediation") == "needs_remediation"
        and not i.get("type", "").startswith("compliant-")
    ]

    # Group issues by WCAG criterion
    issues_by_criterion: Dict[str, List[Dict[str, Any]]] = {}
    for issue in active_issues:
        criterion = issue.get("wcag_criterion", "unknown")
        if criterion not in issues_by_criterion:
            issues_by_criterion[criterion] = []
        issues_by_criterion[criterion].append(issue)

    # Filter to criteria at or below target level
    max_level_value = WCAG_LEVELS.get(target_level.upper(), 2)
    criteria_at_level = {
        criterion: issues_list
        for criterion, issues_list in issues_by_criterion.items()
        if criterion != "unknown"
        and WCAG_LEVELS.get(get_criterion_info(criterion).get("level", "A"), 1)
        <= max_level_value
    }

    # Check for critical/major issues (these mean non-compliance)
    has_blocking_issues = False
    for criterion, criterion_issues in criteria_at_level.items():
        for issue in criterion_issues:
            severity = issue.get("severity", "minor").lower()
            if severity in ["critical", "major"]:
                has_blocking_issues = True
                break
        if has_blocking_issues:
            break

    # Calculate compliance - no critical/major issues at target level
    is_compliant = len(criteria_at_level) == 0 or not has_blocking_issues

    return {
        "compliant": is_compliant,
        "target_level": target_level.upper(),
        "criteria_with_issues": len(criteria_at_level),
        "total_issues_at_level": sum(len(v) for v in criteria_at_level.values()),
        "issues_by_criterion": {
            k: len(v) for k, v in criteria_at_level.items()
        },
        "failing_criteria": list(criteria_at_level.keys()),
    }


def get_conformance_summary(audit_report: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate a comprehensive conformance summary from an audit report.

    Args:
        audit_report: Complete audit report dictionary

    Returns:
        Dictionary with conformance levels and compliance information
    """
    issues = audit_report.get("issues", [])

    # Calculate conformance summary
    conformance = calculate_conformance_summary(issues)

    # Check compliance at each level
    level_a_compliance = calculate_wcag_compliance(issues, "A")
    level_aa_compliance = calculate_wcag_compliance(issues, "AA")
    level_aaa_compliance = calculate_wcag_compliance(issues, "AAA")

    return {
        "conformance": conformance,
        "compliance": {
            "level_a": level_a_compliance,
            "level_aa": level_aa_compliance,
            "level_aaa": level_aaa_compliance,
        },
        "recommendation": _get_recommendation(conformance, level_aa_compliance),
    }


# Backwards compatibility alias
get_score_summary = get_conformance_summary


def _get_recommendation(
    conformance: Dict[str, Any],
    level_aa_compliance: Dict[str, Any],
) -> str:
    """
    Generate a recommendation based on conformance results.

    Args:
        conformance: Conformance calculation result
        level_aa_compliance: Level AA compliance result

    Returns:
        Recommendation string
    """
    critical = conformance["issues_by_severity"]["critical"]
    major = conformance["issues_by_severity"]["major"]

    if critical > 0:
        return (
            f"Address {critical} critical issue(s) immediately. "
            "These prevent basic accessibility for many users."
        )
    elif major > 5:
        return (
            f"Prioritize fixing {major} major issues. "
            "Focus on WCAG Level A and AA criteria first."
        )
    elif not level_aa_compliance["compliant"]:
        failing = len(level_aa_compliance["failing_criteria"])
        return (
            f"Address issues in {failing} WCAG criteria to improve conformance. "
            "Review the conformance_by_criterion breakdown for details."
        )
    else:
        return (
            "Good conformance status. Monitor for regressions and "
            "consider addressing any remaining minor issues."
        )
