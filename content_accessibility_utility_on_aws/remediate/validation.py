# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Post-remediation validation module.

This module provides functionality to validate that remediation was successful
by re-auditing the HTML after remediation and comparing results.
"""

from typing import Dict, List, Any, Optional, Set
from content_accessibility_utility_on_aws.utils.logging_helper import setup_logger

# Set up module-level logger
logger = setup_logger(__name__)


class RemediationValidator:
    """Validates that remediation was successful by comparing pre and post audit results."""

    def __init__(self, auditor_class=None):
        """
        Initialize the remediation validator.

        Args:
            auditor_class: The auditor class to use for re-auditing.
                          If None, will import AccessibilityAuditor.
        """
        if auditor_class is None:
            from content_accessibility_utility_on_aws.audit.auditor import AccessibilityAuditor
            auditor_class = AccessibilityAuditor
        self.auditor_class = auditor_class

    def validate_remediation(
        self,
        original_html: str,
        remediated_html: str,
        original_issues: List[Dict[str, Any]],
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Validate remediation by comparing pre and post audit results.

        Args:
            original_html: The original HTML content before remediation.
            remediated_html: The HTML content after remediation.
            original_issues: List of issues from the original audit.
            options: Auditor options for re-auditing.

        Returns:
            Dictionary containing validation results:
                - fixed_count: Number of issues that were fixed
                - remaining_count: Number of original issues still present
                - new_issues_count: Number of new issues introduced
                - success_rate: Percentage of original issues fixed (0.0-1.0)
                - fixed_issues: List of issues that were fixed
                - remaining_issues: List of issues still present
                - new_issues: List of new issues introduced
                - validation_passed: Boolean indicating if validation passed
        """
        logger.info("Starting post-remediation validation...")

        # Re-audit the remediated HTML
        auditor = self.auditor_class(html_content=remediated_html, options=options)
        new_report = auditor.audit()
        new_issues = new_report.get("issues", [])

        # Filter to only issues that need remediation
        original_needs_remediation = [
            i for i in original_issues
            if i.get("remediation_status") == "needs_remediation"
        ]
        new_needs_remediation = [
            i for i in new_issues
            if i.get("remediation_status") == "needs_remediation"
        ]

        logger.debug(
            f"Original issues needing remediation: {len(original_needs_remediation)}"
        )
        logger.debug(f"New issues needing remediation: {len(new_needs_remediation)}")

        # Find fixed issues (present in original but not in new)
        fixed_issues = self._find_fixed_issues(
            original_needs_remediation, new_needs_remediation
        )

        # Find remaining issues (present in both original and new)
        remaining_issues = self._find_remaining_issues(
            original_needs_remediation, new_needs_remediation
        )

        # Find new issues (present in new but not in original)
        introduced_issues = self._find_new_issues(
            original_needs_remediation, new_needs_remediation
        )

        # Calculate success rate
        if len(original_needs_remediation) > 0:
            success_rate = len(fixed_issues) / len(original_needs_remediation)
        else:
            success_rate = 1.0

        # Determine if validation passed (success rate threshold can be configured)
        validation_passed = success_rate >= 0.5 and len(introduced_issues) == 0

        result = {
            "fixed_count": len(fixed_issues),
            "remaining_count": len(remaining_issues),
            "new_issues_count": len(introduced_issues),
            "success_rate": round(success_rate, 4),
            "success_rate_percent": round(success_rate * 100, 2),
            "fixed_issues": fixed_issues,
            "remaining_issues": remaining_issues,
            "new_issues": introduced_issues,
            "validation_passed": validation_passed,
            "summary": {
                "original_issues": len(original_needs_remediation),
                "issues_fixed": len(fixed_issues),
                "issues_remaining": len(remaining_issues),
                "issues_introduced": len(introduced_issues),
            },
        }

        logger.info(
            f"Validation complete: {len(fixed_issues)} fixed, "
            f"{len(remaining_issues)} remaining, {len(introduced_issues)} new issues"
        )
        logger.info(f"Success rate: {result['success_rate_percent']}%")

        return result

    def _find_fixed_issues(
        self, original_issues: List[Dict], new_issues: List[Dict]
    ) -> List[Dict]:
        """
        Find issues that were present in original but not in new.

        Args:
            original_issues: Original list of issues.
            new_issues: New list of issues after remediation.

        Returns:
            List of issues that were fixed.
        """
        new_issue_keys = self._get_issue_keys(new_issues)
        fixed = []

        for issue in original_issues:
            key = self._get_issue_key(issue)
            if key not in new_issue_keys:
                fixed.append({
                    **issue,
                    "validation_status": "fixed",
                })

        return fixed

    def _find_remaining_issues(
        self, original_issues: List[Dict], new_issues: List[Dict]
    ) -> List[Dict]:
        """
        Find issues that are present in both original and new.

        Args:
            original_issues: Original list of issues.
            new_issues: New list of issues after remediation.

        Returns:
            List of issues still present.
        """
        new_issue_keys = self._get_issue_keys(new_issues)
        remaining = []

        for issue in original_issues:
            key = self._get_issue_key(issue)
            if key in new_issue_keys:
                remaining.append({
                    **issue,
                    "validation_status": "remaining",
                })

        return remaining

    def _find_new_issues(
        self, original_issues: List[Dict], new_issues: List[Dict]
    ) -> List[Dict]:
        """
        Find issues that are in new but not in original.

        Args:
            original_issues: Original list of issues.
            new_issues: New list of issues after remediation.

        Returns:
            List of newly introduced issues.
        """
        original_issue_keys = self._get_issue_keys(original_issues)
        introduced = []

        for issue in new_issues:
            key = self._get_issue_key(issue)
            if key not in original_issue_keys:
                introduced.append({
                    **issue,
                    "validation_status": "introduced",
                })

        return introduced

    def _get_issue_key(self, issue: Dict) -> str:
        """
        Generate a unique key for an issue for comparison.

        Keys are based on issue type and location/context to match similar issues.

        Args:
            issue: The issue dictionary.

        Returns:
            A string key uniquely identifying the issue.
        """
        issue_type = issue.get("type", "")
        wcag = issue.get("wcag_criterion", "")

        # Try to get location information
        location = issue.get("location", {}) or {}
        path = location.get("path", "") if isinstance(location, dict) else ""
        page = location.get("page_number", "") if isinstance(location, dict) else ""

        # Create a composite key
        return f"{issue_type}:{wcag}:{path}:{page}"

    def _get_issue_keys(self, issues: List[Dict]) -> Set[str]:
        """
        Get a set of keys for a list of issues.

        Args:
            issues: List of issue dictionaries.

        Returns:
            Set of issue keys.
        """
        return {self._get_issue_key(issue) for issue in issues}


def validate_remediation(
    original_html: str,
    remediated_html: str,
    original_issues: List[Dict[str, Any]],
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Convenience function to validate remediation.

    Args:
        original_html: The original HTML content before remediation.
        remediated_html: The HTML content after remediation.
        original_issues: List of issues from the original audit.
        options: Auditor options for re-auditing.

    Returns:
        Dictionary containing validation results.
    """
    validator = RemediationValidator()
    return validator.validate_remediation(
        original_html, remediated_html, original_issues, options
    )
