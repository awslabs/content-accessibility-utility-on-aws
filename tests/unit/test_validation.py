# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Unit tests for the post-remediation validation module.
"""

import pytest
from content_accessibility_utility_on_aws.remediate.validation import (
    RemediationValidator,
    validate_remediation,
)


class TestRemediationValidator:
    """Tests for the RemediationValidator class."""

    @pytest.fixture
    def validator(self):
        """Create a validator instance."""
        return RemediationValidator()

    def test_validate_all_issues_fixed(self, validator):
        """Test validation when all issues are fixed."""
        original_html = '<html><body><img src="test.png"></body></html>'
        remediated_html = '<html><body><img src="test.png" alt="Test image"></body></html>'

        original_issues = [
            {
                "type": "missing_alt_text",
                "wcag_criterion": "1.1.1",
                "severity": "critical",
                "remediation_status": "needs_remediation",
                "location": {"path": "/html/body/img"},
            }
        ]

        # Mock the auditor to return no issues
        class MockAuditor:
            def __init__(self, html_content=None, options=None):
                pass

            def audit(self):
                return {"issues": []}

        validator.auditor_class = MockAuditor
        result = validator.validate_remediation(
            original_html, remediated_html, original_issues
        )

        assert result["fixed_count"] == 1
        assert result["remaining_count"] == 0
        assert result["new_issues_count"] == 0
        assert result["success_rate"] == 1.0
        assert result["validation_passed"] is True

    def test_validate_no_issues_fixed(self, validator):
        """Test validation when no issues are fixed."""
        original_html = '<html><body><img src="test.png"></body></html>'
        remediated_html = '<html><body><img src="test.png"></body></html>'

        original_issues = [
            {
                "type": "missing_alt_text",
                "wcag_criterion": "1.1.1",
                "severity": "critical",
                "remediation_status": "needs_remediation",
                "location": {"path": "/html/body/img"},
            }
        ]

        # Mock the auditor to return the same issue
        class MockAuditor:
            def __init__(self, html_content=None, options=None):
                pass

            def audit(self):
                return {
                    "issues": [
                        {
                            "type": "missing_alt_text",
                            "wcag_criterion": "1.1.1",
                            "severity": "critical",
                            "remediation_status": "needs_remediation",
                            "location": {"path": "/html/body/img"},
                        }
                    ]
                }

        validator.auditor_class = MockAuditor
        result = validator.validate_remediation(
            original_html, remediated_html, original_issues
        )

        assert result["fixed_count"] == 0
        assert result["remaining_count"] == 1
        assert result["success_rate"] == 0.0
        assert result["validation_passed"] is False

    def test_validate_partial_fix(self, validator):
        """Test validation when some issues are fixed."""
        original_html = '<html><body><img src="a.png"><img src="b.png"></body></html>'
        remediated_html = '<html><body><img src="a.png" alt="A"><img src="b.png"></body></html>'

        original_issues = [
            {
                "type": "missing_alt_text",
                "wcag_criterion": "1.1.1",
                "severity": "critical",
                "remediation_status": "needs_remediation",
                "location": {"path": "/html/body/img[1]"},
            },
            {
                "type": "missing_alt_text",
                "wcag_criterion": "1.1.1",
                "severity": "critical",
                "remediation_status": "needs_remediation",
                "location": {"path": "/html/body/img[2]"},
            },
        ]

        # Mock the auditor to return one remaining issue
        class MockAuditor:
            def __init__(self, html_content=None, options=None):
                pass

            def audit(self):
                return {
                    "issues": [
                        {
                            "type": "missing_alt_text",
                            "wcag_criterion": "1.1.1",
                            "severity": "critical",
                            "remediation_status": "needs_remediation",
                            "location": {"path": "/html/body/img[2]"},
                        }
                    ]
                }

        validator.auditor_class = MockAuditor
        result = validator.validate_remediation(
            original_html, remediated_html, original_issues
        )

        assert result["fixed_count"] == 1
        assert result["remaining_count"] == 1
        assert result["success_rate"] == 0.5
        assert result["validation_passed"] is True  # 50% is the threshold

    def test_validate_new_issues_introduced(self, validator):
        """Test validation when new issues are introduced."""
        original_html = '<html lang="en"><body><img src="test.png" alt="Test"></body></html>'
        remediated_html = '<html><body><img src="test.png" alt="Test"></body></html>'

        original_issues = []  # No original issues

        # Mock the auditor to return a new issue (language removed)
        class MockAuditor:
            def __init__(self, html_content=None, options=None):
                pass

            def audit(self):
                return {
                    "issues": [
                        {
                            "type": "missing-language",
                            "wcag_criterion": "3.1.1",
                            "severity": "critical",
                            "remediation_status": "needs_remediation",
                            "location": {"path": "/html"},
                        }
                    ]
                }

        validator.auditor_class = MockAuditor
        result = validator.validate_remediation(
            original_html, remediated_html, original_issues
        )

        assert result["new_issues_count"] == 1
        assert result["validation_passed"] is False  # New issues mean failure

    def test_empty_original_issues(self, validator):
        """Test validation with no original issues."""
        original_html = '<html lang="en"><body></body></html>'
        remediated_html = '<html lang="en"><body></body></html>'

        original_issues = []

        class MockAuditor:
            def __init__(self, html_content=None, options=None):
                pass

            def audit(self):
                return {"issues": []}

        validator.auditor_class = MockAuditor
        result = validator.validate_remediation(
            original_html, remediated_html, original_issues
        )

        assert result["success_rate"] == 1.0
        assert result["validation_passed"] is True


class TestValidateRemediationFunction:
    """Tests for the validate_remediation convenience function."""

    def test_convenience_function_works(self, mocker):
        """Test that the convenience function works."""
        # Mock the AccessibilityAuditor
        mock_auditor = mocker.MagicMock()
        mock_auditor.audit.return_value = {"issues": []}

        mocker.patch(
            "content_accessibility_utility_on_aws.remediate.validation.RemediationValidator.__init__",
            return_value=None,
        )
        mocker.patch(
            "content_accessibility_utility_on_aws.remediate.validation.RemediationValidator.validate_remediation",
            return_value={
                "fixed_count": 1,
                "remaining_count": 0,
                "new_issues_count": 0,
                "success_rate": 1.0,
                "validation_passed": True,
            },
        )

        result = validate_remediation(
            original_html="<html></html>",
            remediated_html="<html></html>",
            original_issues=[],
        )

        assert "fixed_count" in result
        assert "validation_passed" in result


class TestIssueKeyGeneration:
    """Tests for issue key generation used in comparison."""

    @pytest.fixture
    def validator(self):
        """Create a validator instance."""
        return RemediationValidator()

    def test_issue_key_includes_type(self, validator):
        """Test that issue key includes the type."""
        issue = {"type": "missing_alt_text", "wcag_criterion": "1.1.1"}
        key = validator._get_issue_key(issue)
        assert "missing_alt_text" in key

    def test_issue_key_includes_wcag(self, validator):
        """Test that issue key includes WCAG criterion."""
        issue = {"type": "missing_alt_text", "wcag_criterion": "1.1.1"}
        key = validator._get_issue_key(issue)
        assert "1.1.1" in key

    def test_same_issues_have_same_key(self, validator):
        """Test that identical issues have the same key."""
        issue1 = {
            "type": "missing_alt_text",
            "wcag_criterion": "1.1.1",
            "location": {"path": "/html/body/img"},
        }
        issue2 = {
            "type": "missing_alt_text",
            "wcag_criterion": "1.1.1",
            "location": {"path": "/html/body/img"},
        }
        assert validator._get_issue_key(issue1) == validator._get_issue_key(issue2)

    def test_different_issues_have_different_keys(self, validator):
        """Test that different issues have different keys."""
        issue1 = {
            "type": "missing_alt_text",
            "wcag_criterion": "1.1.1",
            "location": {"path": "/html/body/img[1]"},
        }
        issue2 = {
            "type": "missing-language",
            "wcag_criterion": "3.1.1",
            "location": {"path": "/html"},
        }
        assert validator._get_issue_key(issue1) != validator._get_issue_key(issue2)
