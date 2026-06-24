# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Phase 2 — rule-based remediation tests (offline, no model).

The core guarantee here is the audit -> remediate -> re-audit loop: after
remediating, the issue should no longer be reported. This is exactly the kind
of test that would have caught the _find_target bug (remediation silently
returning None on multi-element pages).
"""

from bs4 import BeautifulSoup

from content_accessibility_utility_on_aws.remediate.remediation_manager import (
    RemediationManager,
)
from content_accessibility_utility_on_aws.remediate.remediation_strategies.target_size_remediation import (
    remediate_target_size_too_small,
)
from content_accessibility_utility_on_aws.utils.css_dimensions import declared_dimension
from tests.conftest import audit_html, has_issue_type, issues_of_type, make_issue


def remediate_all(html, issue_types=None):
    """
    Audit, remediate every needs-remediation issue offline, and return the
    re-audited report of the remediated document.
    """
    report = audit_html(html)
    mgr = RemediationManager(BeautifulSoup(html, "html.parser"), options={"disable_ai": True})
    for issue in report["issues"]:
        if issue.get("remediation_status") == "compliant":
            continue
        if issue_types and issue["type"] not in issue_types:
            continue
        mgr.remediate_issue(issue)
    return str(mgr.soup), audit_html(str(mgr.soup))


# --- Target size (the regression-prone path) --------------------------------


def test_target_size_remediated_on_multi_button_page():
    # Two buttons, one undersized: the fixed resolver must still find the right
    # one even though find_all('button') returns more than one.
    html = (
        "<html><body><main>"
        "<button style='width:10px;height:10px'>B1</button>"
        "<button>Normal</button>"
        "</main></body></html>"
    )
    report = audit_html(html)
    issue = issues_of_type(report, "target-size-too-small")[0]
    soup = BeautifulSoup(html, "html.parser")
    result = remediate_target_size_too_small(soup, issue)
    assert result is not None  # was None before the fix


def test_target_size_important_is_overridden():
    soup = BeautifulSoup(
        "<html><body><div><button style='width:10px !important;color:red'>x</button></div></body></html>",
        "html.parser",
    )
    issue = make_issue("target-size-too-small", path="html > body > div > button", element="button")
    result = remediate_target_size_too_small(soup, issue)
    assert result is not None
    btn = soup.find("button")
    # Undersized !important width stripped; enforced min-width now governs.
    assert declared_dimension(btn, "width") == 24.0
    assert "color:red" in btn.get("style")


def test_target_size_reaudit_clears_issue():
    html = "<html><body><div><button style='width:8px;height:8px'>x</button></div></body></html>"
    _, report = remediate_all(html, issue_types={"target-size-too-small"})
    assert not has_issue_type(report, "target-size-too-small")


# --- Document structure -----------------------------------------------------


def test_missing_language_remediated():
    html = "<html><body><p>Text</p></body></html>"
    fixed_html, report = remediate_all(html, issue_types={"missing-document-language"})
    assert 'lang="en"' in fixed_html
    assert not has_issue_type(report, "missing-document-language")


def test_missing_title_remediated():
    html = "<html><head></head><body><h1>Annual Report</h1></body></html>"
    fixed_html, report = remediate_all(html, issue_types={"missing-page-title", "missing-title"})
    assert "<title>" in fixed_html


# --- Links ------------------------------------------------------------------


def test_generic_link_text_remediated_rule_based():
    html = "<html><body><p>Download. <a href='https://ex.com/r'>click here</a></p></body></html>"
    report = audit_html(html)
    issue = issues_of_type(report, "generic-link-text")[0]
    mgr = RemediationManager(BeautifulSoup(html, "html.parser"), options={"disable_ai": True})
    result = mgr.remediate_issue(issue)
    assert result is not None  # was unreachable before the fix
    # No model -> rule-based descriptive text replaces "click here".
    link = mgr.soup.find("a", href="https://ex.com/r")
    assert link.get_text(strip=True).lower() != "click here"


def test_empty_link_text_remediated():
    html = "<html><body><div><a href='https://ex.com/page'></a></div></body></html>"
    report = audit_html(html)
    issues = issues_of_type(report, "empty-link-text")
    assert issues
    mgr = RemediationManager(BeautifulSoup(html, "html.parser"), options={"disable_ai": True})
    mgr.remediate_issue(issues[0])
    link = mgr.soup.find("a", href="https://ex.com/page")
    assert link.get_text(strip=True) != ""


# --- Headings ---------------------------------------------------------------


def test_table_remediation_uses_fallback_when_ai_disabled():
    # Regression: with disable_ai=True the manager must NOT force-create a
    # Bedrock client for table issues (which would make real AWS calls); table
    # remediation should use its rule-based fallback instead.
    html = (
        "<html><body><table>"
        "<tr><th>Name</th><th>Age</th></tr>"
        "<tr><td>Sam</td><td>30</td></tr>"
        "</table></body></html>"
    )
    report = audit_html(html)
    table_issues = [i for i in report["issues"] if i["type"].startswith("table-")]
    assert table_issues
    mgr = RemediationManager(BeautifulSoup(html, "html.parser"), options={"disable_ai": True})
    # No client should have been constructed.
    assert mgr.bedrock_client is None
    for issue in table_issues:
        # Should return a result via the fallback path without raising/hanging.
        mgr.remediate_issue(issue)
    # The manager still has not constructed a Bedrock client.
    assert mgr.bedrock_client is None


def test_empty_heading_remediated_rule_based():
    html = (
        "<html><body><h2 id='h'></h2>"
        "<p>Revenue grew across all regions this quarter.</p></body></html>"
    )
    report = audit_html(html)
    issues = issues_of_type(report, "empty-heading")
    assert issues
    mgr = RemediationManager(BeautifulSoup(html, "html.parser"), options={"disable_ai": True})
    mgr.remediate_issue(issues[0])
    heading = mgr.soup.find("h2", id="h")
    assert heading.get_text(strip=True) != ""
