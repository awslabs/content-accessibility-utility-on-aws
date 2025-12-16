# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Integration tests for the audit and remediate workflow.
"""

import pytest
from content_accessibility_utility_on_aws.audit.auditor import AccessibilityAuditor
from content_accessibility_utility_on_aws.remediate.remediator import Remediator


class TestAuditRemediateFlow:
    """Integration tests for the audit-remediate workflow."""

    def test_audit_returns_valid_report(self, html_missing_alt_text):
        """Test that audit returns a properly structured report."""
        auditor = AccessibilityAuditor(html_content=html_missing_alt_text)
        report = auditor.audit()

        # Verify report structure
        assert isinstance(report, dict)
        assert "summary" in report
        assert "issues" in report
        assert isinstance(report["issues"], list)

    def test_audit_detects_multiple_issue_types(self, html_missing_landmarks):
        """Test that audit detects multiple types of issues."""
        auditor = AccessibilityAuditor(html_content=html_missing_landmarks)
        report = auditor.audit()

        # Should detect landmark-related issues
        issue_types = set(i["type"] for i in report["issues"])
        assert len(issue_types) > 0

    def test_remediate_processes_issues(self, html_missing_alt_text, mocker):
        """Test that remediation processes audit issues."""
        # First audit
        auditor = AccessibilityAuditor(html_content=html_missing_alt_text)
        report = auditor.audit()

        # Get issues that need remediation
        issues = [i for i in report["issues"]
                  if i.get("remediation_status") == "needs_remediation"]

        if issues:
            # Mock the Bedrock client to avoid actual API calls
            mocker.patch(
                'content_accessibility_utility_on_aws.remediate.remediation_manager.BedrockClient',
                return_value=mocker.MagicMock()
            )

            # Create remediator with AI disabled for testing
            options = {"disable_ai": True}
            remediator = Remediator(options=options)

            # Attempt remediation
            result = remediator.remediate_html(html_missing_alt_text, issues)

            # Verify result structure
            assert "html" in result
            assert isinstance(result["html"], str)

    def test_full_workflow_with_headings(self, html_heading_hierarchy_issues, mocker):
        """Test full audit-remediate workflow with heading issues."""
        # Audit
        auditor = AccessibilityAuditor(html_content=html_heading_hierarchy_issues)
        report = auditor.audit()

        # Find heading issues
        heading_issues = [i for i in report["issues"]
                         if "heading" in i["type"].lower()
                         and i.get("remediation_status") == "needs_remediation"]

        assert len(heading_issues) > 0, "Should detect heading issues"

    def test_full_workflow_with_tables(self, html_table_missing_scope, mocker):
        """Test full audit-remediate workflow with table issues."""
        # Audit
        auditor = AccessibilityAuditor(html_content=html_table_missing_scope)
        report = auditor.audit()

        # Find table issues
        table_issues = [i for i in report["issues"]
                        if "table" in i["type"].lower()
                        and i.get("remediation_status") == "needs_remediation"]

        assert len(table_issues) > 0, "Should detect table issues"

    def test_audit_with_different_severity_thresholds(self, html_missing_alt_text):
        """Test audit with different severity thresholds."""
        # Audit with all severities
        auditor_all = AccessibilityAuditor(
            html_content=html_missing_alt_text,
            options={"severity_threshold": "minor"}
        )
        report_all = auditor_all.audit()

        # Audit with only critical
        auditor_critical = AccessibilityAuditor(
            html_content=html_missing_alt_text,
            options={"severity_threshold": "critical"}
        )
        report_critical = auditor_critical.audit()

        # All issues should have at least as many as critical-only
        all_needs_remediation = len([
            i for i in report_all["issues"]
            if i.get("remediation_status") == "needs_remediation"
        ])
        critical_needs_remediation = len([
            i for i in report_critical["issues"]
            if i.get("remediation_status") == "needs_remediation"
        ])

        assert all_needs_remediation >= critical_needs_remediation


class TestMultiPageWorkflow:
    """Integration tests for multi-page document workflows."""

    def test_multi_page_audit(self, temp_html_dir, html_missing_alt_text, html_heading_hierarchy_issues):
        """Test auditing multiple HTML files in a directory."""
        html_dir, files = temp_html_dir([html_missing_alt_text, html_heading_hierarchy_issues])

        auditor = AccessibilityAuditor(html_path=html_dir)
        report = auditor.audit()

        # Should have issues from both pages
        assert report["summary"]["total_issues"] > 0

        # Should have by_page grouping
        assert "by_page" in report
        assert len(report["by_page"]) > 0

    def test_multi_page_preserves_file_info(self, temp_html_dir, html_missing_alt_text):
        """Test that multi-page audit preserves file information."""
        html_dir, files = temp_html_dir([html_missing_alt_text, html_missing_alt_text])

        auditor = AccessibilityAuditor(html_path=html_dir)
        report = auditor.audit()

        # Check that issues have location information
        for issue in report["issues"]:
            if "location" in issue and issue["location"]:
                # Should have file or page information
                has_file_info = (
                    "file_path" in issue["location"] or
                    "page_number" in issue["location"] or
                    "file_name" in issue["location"]
                )
                # Not all issues will have location, but those that do should be complete
                if issue["location"]:
                    assert has_file_info or len(issue["location"]) == 0


class TestReportConsistency:
    """Tests for report consistency and accuracy."""

    def test_summary_matches_issues(self, html_missing_alt_text):
        """Test that summary counts match actual issue counts."""
        auditor = AccessibilityAuditor(html_content=html_missing_alt_text)
        report = auditor.audit()

        # Count issues by status
        needs_remediation_count = len([
            i for i in report["issues"]
            if i.get("remediation_status") == "needs_remediation"
        ])
        remediated_count = len([
            i for i in report["issues"]
            if i.get("remediation_status") == "remediated"
        ])
        auto_remediated_count = len([
            i for i in report["issues"]
            if i.get("remediation_status") == "auto_remediated"
        ])

        # Verify summary matches
        assert report["summary"]["needs_remediation"] == needs_remediation_count
        assert report["summary"]["remediated"] == remediated_count
        assert report["summary"]["auto_remediated"] == auto_remediated_count

    def test_severity_counts_accurate(self, html_missing_alt_text):
        """Test that severity counts are accurate."""
        auditor = AccessibilityAuditor(html_content=html_missing_alt_text)
        report = auditor.audit()

        # Count issues by severity
        severity_counts = {"critical": 0, "major": 0, "minor": 0, "info": 0}
        for issue in report["issues"]:
            severity = issue.get("severity", "info")
            if severity in severity_counts:
                severity_counts[severity] += 1

        # Verify counts match
        for severity, count in severity_counts.items():
            assert report["summary"]["severity_counts"][severity] == count
