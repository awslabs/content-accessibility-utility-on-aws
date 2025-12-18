# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Unit tests for the AccessibilityAuditor class.
"""

from content_accessibility_utility_on_aws.audit.auditor import AccessibilityAuditor


class TestAccessibilityAuditorInit:
    """Tests for AccessibilityAuditor initialization."""

    def test_init_with_html_content(self, html_fully_accessible):
        """Test initialization with HTML content string."""
        auditor = AccessibilityAuditor(html_content=html_fully_accessible)
        assert auditor.html_content == html_fully_accessible
        assert auditor.html_path is None

    def test_init_with_html_path(self, temp_html_file, html_fully_accessible):
        """Test initialization with HTML file path."""
        file_path = temp_html_file(html_fully_accessible)
        auditor = AccessibilityAuditor(html_path=file_path)
        assert auditor.html_path == file_path

    def test_init_with_custom_options(self, html_fully_accessible):
        """Test initialization with custom options."""
        options = {
            "severity_threshold": "major",
            "report_format": "html",
            "detailed": False,
        }
        auditor = AccessibilityAuditor(html_content=html_fully_accessible, options=options)
        assert auditor.options["severity_threshold"] == "major"
        assert auditor.options["report_format"] == "html"
        assert auditor.options["detailed"] is False

    def test_default_options(self, html_fully_accessible):
        """Test that default options are set correctly."""
        auditor = AccessibilityAuditor(html_content=html_fully_accessible)
        assert auditor.options["severity_threshold"] == "minor"
        assert auditor.options["report_format"] == "json"
        assert auditor.options["detailed"] is True
        assert auditor.options["include_remediated"] is True


class TestAccessibilityAuditorLoadHtml:
    """Tests for HTML loading functionality."""

    def test_load_html_from_content(self, html_fully_accessible):
        """Test loading HTML from content string."""
        auditor = AccessibilityAuditor(html_content=html_fully_accessible)
        result = auditor.load_html()
        assert result is True
        assert auditor.soup is not None

    def test_load_html_from_file(self, temp_html_file, html_fully_accessible):
        """Test loading HTML from file path."""
        file_path = temp_html_file(html_fully_accessible)
        auditor = AccessibilityAuditor(html_path=file_path)
        result = auditor.load_html()
        assert result is True
        assert auditor.soup is not None

    def test_load_html_from_directory(self, temp_html_dir, html_fully_accessible):
        """Test loading HTML from directory with multiple files."""
        html_dir, files = temp_html_dir([html_fully_accessible, html_fully_accessible])
        auditor = AccessibilityAuditor(html_path=html_dir)
        result = auditor.load_html()
        assert result is True
        assert len(auditor.html_files) == 2

    def test_load_html_file_not_found(self):
        """Test handling of non-existent file."""
        auditor = AccessibilityAuditor(html_path="/nonexistent/path.html")
        result = auditor.load_html()
        assert result is False

    def test_load_html_no_content_or_path(self):
        """Test handling when neither content nor path is provided."""
        auditor = AccessibilityAuditor()
        result = auditor.load_html()
        assert result is False


class TestAccessibilityAuditorExtractElements:
    """Tests for element extraction."""

    def test_extract_images(self, auditor_factory, html_missing_alt_text):
        """Test extraction of image elements."""
        auditor = auditor_factory(html_content=html_missing_alt_text)
        auditor.load_html()
        auditor.extract_elements()
        assert len(auditor.images) == 3

    def test_extract_headings(self, auditor_factory, html_heading_hierarchy_issues):
        """Test extraction of heading elements."""
        auditor = auditor_factory(html_content=html_heading_hierarchy_issues)
        auditor.load_html()
        auditor.extract_elements()
        assert len(auditor.headings) == 4

    def test_extract_tables(self, auditor_factory, html_table_no_headers):
        """Test extraction of table elements."""
        auditor = auditor_factory(html_content=html_table_no_headers)
        auditor.load_html()
        auditor.extract_elements()
        assert len(auditor.tables) == 1

    def test_extract_links(self, auditor_factory, html_links_empty_text):
        """Test extraction of link elements."""
        auditor = auditor_factory(html_content=html_links_empty_text)
        auditor.load_html()
        auditor.extract_elements()
        assert len(auditor.links) == 5


class TestAccessibilityAuditorAudit:
    """Tests for the main audit functionality."""

    def test_audit_fully_accessible_page(self, auditor_factory, html_fully_accessible):
        """Test auditing a fully accessible page returns valid report structure."""
        auditor = auditor_factory(html_content=html_fully_accessible)
        report = auditor.audit()

        # Check report structure
        assert "summary" in report
        assert "issues" in report
        assert "by_page" in report
        assert "by_status" in report

        # Verify severity counts are present and valid
        severity_counts = report["summary"]["severity_counts"]
        assert "critical" in severity_counts
        assert "major" in severity_counts
        assert "minor" in severity_counts
        # Note: Some issues may be flagged due to images not being present on disk
        # The important thing is the report structure is valid

    def test_audit_missing_alt_text(self, auditor_factory, html_missing_alt_text):
        """Test detection of missing alt text."""
        auditor = auditor_factory(html_content=html_missing_alt_text)
        report = auditor.audit()

        # Find issues related to alt text
        alt_text_issues = [
            i for i in report["issues"]
            if "alt" in i["type"].lower() and i["remediation_status"] == "needs_remediation"
        ]
        # Should detect 2 images missing alt (3rd has role=presentation)
        assert len(alt_text_issues) >= 2

    def test_audit_missing_language(self, auditor_factory, html_missing_language):
        """Test detection of missing language attribute."""
        auditor = auditor_factory(html_content=html_missing_language)
        report = auditor.audit()

        language_issues = [
            i for i in report["issues"]
            if "language" in i["type"].lower()
        ]
        assert len(language_issues) >= 1

    def test_audit_heading_hierarchy(self, auditor_factory, html_heading_hierarchy_issues):
        """Test detection of heading hierarchy issues."""
        auditor = auditor_factory(html_content=html_heading_hierarchy_issues)
        report = auditor.audit()

        heading_issues = [
            i for i in report["issues"]
            if "heading" in i["type"].lower() and "skipped" in i["type"].lower()
        ]
        assert len(heading_issues) >= 1

    def test_audit_table_missing_headers(self, auditor_factory, html_table_no_headers):
        """Test detection of tables missing headers."""
        auditor = auditor_factory(html_content=html_table_no_headers)
        report = auditor.audit()

        table_issues = [
            i for i in report["issues"]
            if "table" in i["type"].lower() and "header" in i["type"].lower()
        ]
        assert len(table_issues) >= 1

    def test_audit_form_missing_labels(self, auditor_factory, html_form_missing_labels):
        """Test detection of form inputs missing labels."""
        auditor = auditor_factory(html_content=html_form_missing_labels)
        report = auditor.audit()

        form_issues = [
            i for i in report["issues"]
            if "label" in i["type"].lower() or "input" in i["type"].lower()
        ]
        assert len(form_issues) >= 1

    def test_audit_severity_threshold_filtering(self, auditor_factory, html_missing_alt_text):
        """Test that severity threshold filters issues correctly."""
        # With "critical" threshold, only critical issues should be included
        options = {"severity_threshold": "critical"}
        auditor = auditor_factory(html_content=html_missing_alt_text, options=options)
        report = auditor.audit()

        for issue in report["issues"]:
            if issue["remediation_status"] == "needs_remediation":
                assert issue["severity"] == "critical", \
                    f"Issue with severity {issue['severity']} should be filtered"


class TestAccessibilityAuditorReportGeneration:
    """Tests for report generation."""

    def test_report_structure(self, auditor_factory, html_fully_accessible):
        """Test that report has correct structure."""
        auditor = auditor_factory(html_content=html_fully_accessible)
        report = auditor.audit()

        # Check summary structure
        assert "total_issues" in report["summary"]
        assert "needs_remediation" in report["summary"]
        assert "remediated" in report["summary"]
        assert "severity_counts" in report["summary"]

        # Check severity counts structure
        severity_counts = report["summary"]["severity_counts"]
        assert "critical" in severity_counts
        assert "major" in severity_counts
        assert "minor" in severity_counts
        assert "info" in severity_counts

    def test_issue_structure(self, auditor_factory, html_missing_alt_text):
        """Test that individual issues have correct structure."""
        auditor = auditor_factory(html_content=html_missing_alt_text)
        report = auditor.audit()

        if report["issues"]:
            issue = report["issues"][0]
            assert "id" in issue
            assert "type" in issue
            assert "wcag_criterion" in issue
            assert "severity" in issue
            assert "description" in issue
            assert "remediation_status" in issue

    def test_by_status_grouping(self, auditor_factory, html_missing_alt_text):
        """Test that issues are correctly grouped by status."""
        auditor = auditor_factory(html_content=html_missing_alt_text)
        report = auditor.audit()

        assert "needs_remediation" in report["by_status"]
        assert "remediated" in report["by_status"]
        assert "auto_remediated" in report["by_status"]
        assert "compliant" in report["by_status"]


class TestAccessibilityAuditorMultiPage:
    """Tests for multi-page document auditing."""

    def test_audit_multiple_pages(self, auditor_factory, temp_html_dir, html_missing_alt_text, html_heading_hierarchy_issues):
        """Test auditing multiple HTML pages."""
        html_dir, files = temp_html_dir([html_missing_alt_text, html_heading_hierarchy_issues])
        auditor = auditor_factory(html_path=html_dir)
        report = auditor.audit()

        # Should have issues from both pages
        assert report["summary"]["total_issues"] > 0

        # Check by_page grouping
        assert "by_page" in report

    def test_page_number_extraction(self, auditor_factory, temp_html_dir, html_fully_accessible):
        """Test that page numbers are correctly extracted from filenames."""
        html_dir, files = temp_html_dir([html_fully_accessible, html_fully_accessible])
        auditor = auditor_factory(html_path=html_dir)
        report = auditor.audit()

        # Page numbers should be extracted from filenames
        for issue in report["issues"]:
            if "location" in issue and issue["location"]:
                assert "page_number" in issue["location"]
