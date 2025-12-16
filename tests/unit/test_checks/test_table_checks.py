# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Unit tests for table accessibility checks.
"""

import pytest
from bs4 import BeautifulSoup
from content_accessibility_utility_on_aws.audit.checks.table_checks import (
    TableHeaderCheck,
    TableStructureCheck,
)


class TestTableHeaderCheck:
    """Tests for the TableHeaderCheck class."""

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

    def test_allows_table_with_headers(self, soup_factory, issue_collector):
        """Test that table with proper headers passes."""
        html = '''<html><body>
            <table>
                <tr>
                    <th scope="col">Name</th>
                    <th scope="col">Age</th>
                </tr>
                <tr>
                    <td>John</td>
                    <td>30</td>
                </tr>
            </table>
        </body></html>'''
        soup = soup_factory(html)
        check = TableHeaderCheck(soup, issue_collector)
        check.check()

        header_issues = [i for i in issue_collector.issues
                         if "header" in i["type"].lower()
                         and i["status"] == "needs_remediation"]
        # Should have no missing headers or scope issues
        missing_header_issues = [i for i in header_issues
                                  if "missing-headers" in i["type"]]
        assert len(missing_header_issues) == 0

    def test_detects_table_without_headers(self, soup_factory, issue_collector):
        """Test detection of table without any header cells."""
        html = '''<html><body>
            <table>
                <tr>
                    <td>Name</td>
                    <td>Age</td>
                </tr>
                <tr>
                    <td>John</td>
                    <td>30</td>
                </tr>
            </table>
        </body></html>'''
        soup = soup_factory(html)
        check = TableHeaderCheck(soup, issue_collector)
        check.check()

        header_issues = [i for i in issue_collector.issues
                         if "header" in i["type"].lower()]
        assert len(header_issues) >= 1

    def test_detects_headers_missing_scope(self, soup_factory, issue_collector):
        """Test detection of headers without scope attribute."""
        html = '''<html><body>
            <table>
                <tr>
                    <th>Name</th>
                    <th>Age</th>
                </tr>
                <tr>
                    <td>John</td>
                    <td>30</td>
                </tr>
            </table>
        </body></html>'''
        soup = soup_factory(html)
        check = TableHeaderCheck(soup, issue_collector)
        check.check()

        scope_issues = [i for i in issue_collector.issues
                        if "scope" in i["type"].lower()]
        assert len(scope_issues) >= 1

    def test_ignores_layout_tables(self, soup_factory, issue_collector):
        """Test that layout tables are not flagged."""
        html = '''<html><body>
            <table role="presentation">
                <tr>
                    <td>Layout content</td>
                    <td>More layout</td>
                </tr>
            </table>
        </body></html>'''
        soup = soup_factory(html)
        check = TableHeaderCheck(soup, issue_collector)
        check.check()

        issues = [i for i in issue_collector.issues
                  if i["status"] == "needs_remediation"]
        assert len(issues) == 0

    def test_detects_complex_table_missing_caption(self, soup_factory, issue_collector):
        """Test detection of complex table without caption."""
        html = '''<html><body>
            <table>
                <tr>
                    <th scope="col">Name</th>
                    <th scope="col">Q1</th>
                    <th scope="col">Q2</th>
                </tr>
                <tr>
                    <td rowspan="2">Sales</td>
                    <td>100</td>
                    <td>150</td>
                </tr>
                <tr>
                    <td>200</td>
                    <td>250</td>
                </tr>
            </table>
        </body></html>'''
        soup = soup_factory(html)
        check = TableHeaderCheck(soup, issue_collector)
        check.check()

        caption_issues = [i for i in issue_collector.issues
                          if "caption" in i["type"].lower()]
        assert len(caption_issues) >= 1


class TestTableStructureCheck:
    """Tests for the TableStructureCheck class."""

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

    def test_allows_proper_table_structure(self, soup_factory, issue_collector):
        """Test that proper table structure passes."""
        html = '''<html><body>
            <table>
                <thead>
                    <tr>
                        <th scope="col">Name</th>
                        <th scope="col">Age</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>John</td>
                        <td>30</td>
                    </tr>
                </tbody>
            </table>
        </body></html>'''
        soup = soup_factory(html)
        check = TableStructureCheck(soup, issue_collector)
        check.check()

        structure_issues = [i for i in issue_collector.issues
                            if ("thead" in i["type"].lower() or "tbody" in i["type"].lower())
                            and i["status"] == "needs_remediation"]
        assert len(structure_issues) == 0

    def test_detects_missing_thead(self, soup_factory, issue_collector):
        """Test detection of table missing thead element."""
        html = '''<html><body>
            <table>
                <tr>
                    <th>Name</th>
                    <th>Age</th>
                </tr>
                <tr>
                    <td>John</td>
                    <td>30</td>
                </tr>
            </table>
        </body></html>'''
        soup = soup_factory(html)
        check = TableStructureCheck(soup, issue_collector)
        check.check()

        thead_issues = [i for i in issue_collector.issues
                        if "thead" in i["type"].lower()]
        assert len(thead_issues) >= 1

    def test_detects_missing_tbody(self, soup_factory, issue_collector):
        """Test detection of table missing tbody element."""
        html = '''<html><body>
            <table>
                <thead>
                    <tr>
                        <th>Name</th>
                        <th>Age</th>
                    </tr>
                </thead>
                <tr>
                    <td>John</td>
                    <td>30</td>
                </tr>
            </table>
        </body></html>'''
        soup = soup_factory(html)
        check = TableStructureCheck(soup, issue_collector)
        check.check()

        tbody_issues = [i for i in issue_collector.issues
                        if "tbody" in i["type"].lower()]
        assert len(tbody_issues) >= 1
