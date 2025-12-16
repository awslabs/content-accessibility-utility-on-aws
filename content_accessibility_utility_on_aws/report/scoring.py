# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Accessibility scoring module.

This module provides functionality to calculate accessibility compliance scores
based on audit results and issue severity.
"""

from typing import Dict, List, Any, Optional
from content_accessibility_utility_on_aws.audit.standards import (
    SEVERITY_LEVELS,
    WCAG_LEVELS,
    get_criterion_info,
)


# Severity weights for score calculation
SEVERITY_WEIGHTS = {
    "critical": 15,  # Critical issues have maximum impact
    "major": 8,      # Major issues have significant impact
    "minor": 3,      # Minor issues have moderate impact
    "info": 0,       # Informational issues don't affect score
}

# WCAG level weights for enhanced scoring
LEVEL_WEIGHTS = {
    "A": 1.5,    # Level A issues are most important
    "AA": 1.2,  # Level AA issues are important
    "AAA": 1.0, # Level AAA issues are less critical for compliance
}


def calculate_accessibility_score(
    issues: List[Dict[str, Any]],
    max_score: int = 100,
    include_remediated: bool = False,
) -> Dict[str, Any]:
    """
    Calculate an accessibility compliance score based on issues found.

    The score starts at max_score (100) and deductions are made based on
    the severity and WCAG level of each issue. The score cannot go below 0.

    Args:
        issues: List of accessibility issues from an audit
        max_score: Maximum possible score (default 100)
        include_remediated: Whether to include remediated issues in calculation

    Returns:
        Dictionary containing:
            - score: Numeric score (0-100)
            - grade: Letter grade (A, B, C, D, F)
            - max_score: Maximum possible score
            - deductions: Total points deducted
            - breakdown: Detailed breakdown by severity and level
            - compliance_status: Compliance status description
    """
    # Filter issues to only count those needing remediation (unless include_remediated)
    if include_remediated:
        scored_issues = issues
    else:
        scored_issues = [
            i for i in issues
            if i.get("remediation_status", "needs_remediation") == "needs_remediation"
        ]

    # Calculate deductions
    total_deductions = 0
    severity_breakdown = {"critical": 0, "major": 0, "minor": 0, "info": 0}
    level_breakdown = {"A": 0, "AA": 0, "AAA": 0}

    for issue in scored_issues:
        severity = issue.get("severity", "minor").lower()
        wcag_criterion = issue.get("wcag_criterion", "")

        # Get severity weight
        base_weight = SEVERITY_WEIGHTS.get(severity, 3)

        # Get WCAG level multiplier
        criterion_info = get_criterion_info(wcag_criterion)
        level = criterion_info.get("level", "AA")
        level_multiplier = LEVEL_WEIGHTS.get(level, 1.0)

        # Calculate deduction for this issue
        deduction = base_weight * level_multiplier
        total_deductions += deduction

        # Track breakdown
        severity_breakdown[severity] = severity_breakdown.get(severity, 0) + 1
        if level in level_breakdown:
            level_breakdown[level] += 1

    # Calculate final score (minimum 0)
    score = max(0, max_score - total_deductions)

    # Determine letter grade
    grade = _calculate_grade(score)

    # Determine compliance status
    compliance_status = _get_compliance_status(
        score, severity_breakdown["critical"], severity_breakdown["major"]
    )

    return {
        "score": round(score, 1),
        "grade": grade,
        "max_score": max_score,
        "deductions": round(total_deductions, 1),
        "issues_counted": len(scored_issues),
        "breakdown": {
            "by_severity": severity_breakdown,
            "by_level": level_breakdown,
        },
        "compliance_status": compliance_status,
        "details": {
            "critical_issues": severity_breakdown["critical"],
            "major_issues": severity_breakdown["major"],
            "minor_issues": severity_breakdown["minor"],
            "info_issues": severity_breakdown["info"],
        }
    }


def _calculate_grade(score: float) -> str:
    """
    Convert a numeric score to a letter grade.

    Args:
        score: Numeric score (0-100)

    Returns:
        Letter grade (A, B, C, D, or F)
    """
    if score >= 90:
        return "A"
    elif score >= 80:
        return "B"
    elif score >= 70:
        return "C"
    elif score >= 60:
        return "D"
    else:
        return "F"


def _get_compliance_status(
    score: float,
    critical_count: int,
    major_count: int,
) -> str:
    """
    Determine compliance status based on score and issue counts.

    Args:
        score: Numeric score
        critical_count: Number of critical issues
        major_count: Number of major issues

    Returns:
        Compliance status description
    """
    if critical_count > 0:
        return "Non-compliant (critical issues present)"
    elif major_count > 5:
        return "Non-compliant (multiple major issues)"
    elif score >= 90:
        return "Fully compliant"
    elif score >= 80:
        return "Substantially compliant"
    elif score >= 70:
        return "Partially compliant"
    elif score >= 50:
        return "Minimally compliant"
    else:
        return "Non-compliant"


def calculate_wcag_compliance(
    issues: List[Dict[str, Any]],
    target_level: str = "AA",
) -> Dict[str, Any]:
    """
    Calculate WCAG compliance status for a specific conformance level.

    WCAG compliance requires ALL criteria at or below the target level
    to be met. This function checks which criteria have issues.

    Args:
        issues: List of accessibility issues from an audit
        target_level: Target WCAG level ("A", "AA", or "AAA")

    Returns:
        Dictionary containing:
            - compliant: Boolean indicating full compliance
            - target_level: The target level checked
            - criteria_checked: Number of criteria evaluated
            - criteria_with_issues: Number of criteria with issues
            - issues_by_criterion: Issues grouped by WCAG criterion
    """
    # Only consider issues needing remediation
    active_issues = [
        i for i in issues
        if i.get("remediation_status", "needs_remediation") == "needs_remediation"
    ]

    # Group issues by WCAG criterion
    issues_by_criterion = {}
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

    # Calculate compliance
    is_compliant = len(criteria_at_level) == 0

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


def get_score_summary(audit_report: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate a comprehensive score summary from an audit report.

    Args:
        audit_report: Complete audit report dictionary

    Returns:
        Dictionary with score, grades, and compliance information
    """
    issues = audit_report.get("issues", [])

    # Calculate overall score
    score_result = calculate_accessibility_score(issues)

    # Check compliance at each level
    level_a_compliance = calculate_wcag_compliance(issues, "A")
    level_aa_compliance = calculate_wcag_compliance(issues, "AA")
    level_aaa_compliance = calculate_wcag_compliance(issues, "AAA")

    return {
        "score": score_result,
        "compliance": {
            "level_a": level_a_compliance,
            "level_aa": level_aa_compliance,
            "level_aaa": level_aaa_compliance,
        },
        "recommendation": _get_recommendation(score_result, level_aa_compliance),
    }


def _get_recommendation(
    score_result: Dict[str, Any],
    level_aa_compliance: Dict[str, Any],
) -> str:
    """
    Generate a recommendation based on score and compliance results.

    Args:
        score_result: Score calculation result
        level_aa_compliance: Level AA compliance result

    Returns:
        Recommendation string
    """
    critical = score_result["details"]["critical_issues"]
    major = score_result["details"]["major_issues"]
    score = score_result["score"]

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
            f"Fix {failing} failing criteria to achieve WCAG AA compliance. "
            "Review the issues_by_criterion breakdown for details."
        )
    elif score < 80:
        return (
            "Continue improving accessibility by addressing remaining issues. "
            "Consider WCAG AAA criteria for enhanced accessibility."
        )
    else:
        return (
            "Good accessibility score! Monitor for regressions and "
            "consider WCAG AAA compliance for best-in-class accessibility."
        )
