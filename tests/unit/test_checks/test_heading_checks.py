# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Unit tests for heading accessibility checks.
"""

import pytest
from bs4 import BeautifulSoup
from content_accessibility_utility_on_aws.audit.checks.heading_checks import (
    HeadingHierarchyCheck,
    HeadingContentCheck,
    DocumentTitleCheck,
)


class TestHeadingHierarchyCheck:
    """Tests for the HeadingHierarchyCheck class."""

    @pytest.fixture
    def issue_collector(self):
        """Fixture to collect issues reported by checks."""
        issues = []

        def add_issue(issue_type, wcag_criterion, severity, element=None,
                      description=None, context=None, location=None,
                      status="needs_remediation", remediation_source=None):
            issues.append({
                "type": issue_type,
                "wcag_criterion": wcag_criterion,
                "severity": severity,
                "description": description,
                "status": status,
            })

        add_issue.issues = issues
        return add_issue

    def test_allows_proper_hierarchy(self, soup_factory, issue_collector):
        """Test that proper heading hierarchy passes."""
        html = '''<html><body>
            <h1>Main Title</h1>
            <h2>Section 1</h2>
            <h3>Subsection 1.1</h3>
            <h2>Section 2</h2>
        </body></html>'''
        soup = soup_factory(html)
        check = HeadingHierarchyCheck(soup, issue_collector)
        check.check()

        skip_issues = [i for i in issue_collector.issues
                       if "skip" in i["type"].lower()
                       and i["status"] == "needs_remediation"]
        assert len(skip_issues) == 0

    def test_detects_skipped_levels(self, soup_factory, issue_collector):
        """Test detection of skipped heading levels."""
        html = '''<html><body>
            <h1>Main Title</h1>
            <h3>Skipped h2</h3>
        </body></html>'''
        soup = soup_factory(html)
        check = HeadingHierarchyCheck(soup, issue_collector)
        check.check()

        skip_issues = [i for i in issue_collector.issues
                       if "skip" in i["type"].lower()]
        assert len(skip_issues) >= 1

    def test_detects_missing_h1(self, soup_factory, issue_collector):
        """Test detection of page without h1."""
        html = '''<html><body>
            <h2>Section without H1</h2>
            <p>Content here</p>
        </body></html>'''
        soup = soup_factory(html)
        check = HeadingHierarchyCheck(soup, issue_collector)
        check.check()

        h1_issues = [i for i in issue_collector.issues
                     if "h1" in i["type"].lower() or "no-h1" in i["type"]]
        assert len(h1_issues) >= 1


class TestHeadingContentCheck:
    """Tests for the HeadingContentCheck class."""

    @pytest.fixture
    def issue_collector(self):
        """Fixture to collect issues reported by checks."""
        issues = []

        def add_issue(issue_type, wcag_criterion, severity, element=None,
                      description=None, context=None, location=None,
                      status="needs_remediation", remediation_source=None):
            issues.append({
                "type": issue_type,
                "wcag_criterion": wcag_criterion,
                "severity": severity,
                "description": description,
                "status": status,
            })

        add_issue.issues = issues
        return add_issue

    def test_allows_headings_with_content(self, soup_factory, issue_collector):
        """Test that headings with content pass."""
        html = '''<html><body>
            <h1>Main Title</h1>
            <h2>Section Title</h2>
        </body></html>'''
        soup = soup_factory(html)
        check = HeadingContentCheck(soup, issue_collector)
        check.check()

        empty_issues = [i for i in issue_collector.issues
                        if "empty" in i["type"].lower()
                        and i["status"] == "needs_remediation"]
        assert len(empty_issues) == 0

    def test_detects_empty_headings(self, soup_factory, issue_collector):
        """Test detection of empty headings."""
        html = '''<html><body>
            <h1>Main Title</h1>
            <h2></h2>
        </body></html>'''
        soup = soup_factory(html)
        check = HeadingContentCheck(soup, issue_collector)
        check.check()

        empty_issues = [i for i in issue_collector.issues
                        if "empty" in i["type"].lower()]
        assert len(empty_issues) >= 1

    def test_detects_whitespace_only_headings(self, soup_factory, issue_collector):
        """Test detection of headings with only whitespace."""
        html = '''<html><body>
            <h1>Main Title</h1>
            <h2>   </h2>
        </body></html>'''
        soup = soup_factory(html)
        check = HeadingContentCheck(soup, issue_collector)
        check.check()

        empty_issues = [i for i in issue_collector.issues
                        if "empty" in i["type"].lower() or "generic" in i["type"].lower()]
        assert len(empty_issues) >= 1


class TestDocumentTitleCheck:
    """Tests for the DocumentTitleCheck class."""

    @pytest.fixture
    def issue_collector(self):
        """Fixture to collect issues reported by checks."""
        issues = []

        def add_issue(issue_type, wcag_criterion, severity, element=None,
                      description=None, context=None, location=None,
                      status="needs_remediation", remediation_source=None):
            issues.append({
                "type": issue_type,
                "wcag_criterion": wcag_criterion,
                "severity": severity,
                "description": description,
                "status": status,
            })

        add_issue.issues = issues
        return add_issue

    def test_allows_document_with_title(self, soup_factory, issue_collector):
        """Test that document with title passes."""
        html = '''<html><head><title>Page Title</title></head><body>
            <h1>Content</h1>
        </body></html>'''
        soup = soup_factory(html)
        check = DocumentTitleCheck(soup, issue_collector)
        check.check()

        title_issues = [i for i in issue_collector.issues
                        if "title" in i["type"].lower()
                        and i["status"] == "needs_remediation"]
        assert len(title_issues) == 0

    def test_detects_missing_title(self, soup_factory, issue_collector):
        """Test detection of missing document title."""
        html = '''<html><head></head><body>
            <h1>Content</h1>
        </body></html>'''
        soup = soup_factory(html)
        check = DocumentTitleCheck(soup, issue_collector)
        check.check()

        title_issues = [i for i in issue_collector.issues
                        if "title" in i["type"].lower()]
        assert len(title_issues) >= 1

    def test_detects_empty_title(self, soup_factory, issue_collector):
        """Test detection of empty document title."""
        html = '''<html><head><title></title></head><body>
            <h1>Content</h1>
        </body></html>'''
        soup = soup_factory(html)
        check = DocumentTitleCheck(soup, issue_collector)
        check.check()

        title_issues = [i for i in issue_collector.issues
                        if "title" in i["type"].lower()]
        assert len(title_issues) >= 1
