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
    # Re-audit must confirm the issue is actually resolved (not just that some
    # <title> tag exists — it could be empty or misplaced).
    assert not has_issue_type(report, "missing-title")


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


def test_generic_heading_dispatches_and_is_remediated():
    # Regression: the audit emits "generic-heading" but the registry only had
    # "generic-heading-content", so this issue type was silently skipped.
    html = (
        "<html><body><h1>Heading</h1>"
        "<p>This document describes quarterly sales performance.</p></body></html>"
    )
    report = audit_html(html)
    issues = issues_of_type(report, "generic-heading")
    assert issues
    mgr = RemediationManager(BeautifulSoup(html, "html.parser"), options={"disable_ai": True})
    result = mgr.remediate_issue(issues[0])
    assert result is not None  # was silently skipped before the key was added


def test_related_controls_no_fieldset_dispatches():
    # Regression: the audit emits "form-related-controls-no-fieldset" but the
    # registry only had "missing-fieldset"; and remediate_missing_fieldsets used
    # fragile substring path matching. Both are now fixed.
    html = (
        "<html><body><form>"
        "<input type='radio' name='color' value='r'>"
        "<input type='radio' name='color' value='g'>"
        "</form></body></html>"
    )
    report = audit_html(html)
    issues = issues_of_type(report, "form-related-controls-no-fieldset")
    assert issues
    mgr = RemediationManager(BeautifulSoup(html, "html.parser"), options={"disable_ai": True})
    result = mgr.remediate_issue(issues[0])
    assert result is not None
    # A fieldset should now wrap the related controls.
    assert mgr.soup.find("fieldset") is not None


def test_fieldset_resolves_correct_form_among_many():
    # The migrated resolver must target the audited form, not the first one,
    # even when several forms exist (the multi-element bug class).
    html = (
        "<html><body>"
        "<form id='search'><input type='text' name='q'></form>"
        "<form id='prefs'>"
        "<input type='radio' name='theme' value='light'>"
        "<input type='radio' name='theme' value='dark'>"
        "</form>"
        "</body></html>"
    )
    report = audit_html(html)
    issues = issues_of_type(report, "form-related-controls-no-fieldset")
    assert issues
    mgr = RemediationManager(BeautifulSoup(html, "html.parser"), options={"disable_ai": True})
    mgr.remediate_issue(issues[0])
    # The fieldset must land in the prefs form (which has the related radios),
    # not the search form.
    prefs = mgr.soup.find("form", id="prefs")
    search = mgr.soup.find("form", id="search")
    assert prefs.find("fieldset") is not None
    assert search.find("fieldset") is None


def test_improper_figure_structure_resolves_correct_image():
    # The migrated figure resolver must wrap the audited image, not the first
    # image on the page.
    from content_accessibility_utility_on_aws.remediate.remediation_strategies.figure_remediation import (
        remediate_improper_figure_structure,
    )

    html = (
        "<html><body>"
        "<img src='logo.png' alt='Site logo'>"
        "<div><img src='chart.png' alt='Quarterly sales bar chart'></div>"
        "</body></html>"
    )
    soup = BeautifulSoup(html, "html.parser")
    issue = make_issue(
        "improper-figure-structure",
        path="html > body > div > img",
        element="img",
    )
    result = remediate_improper_figure_structure(soup, issue)
    assert result is not None
    # The chart image (the audited one) is wrapped, not the logo.
    chart = soup.find("img", src="chart.png")
    logo = soup.find("img", src="logo.png")
    assert chart.find_parent("figure") is not None
    assert logo.find_parent("figure") is None
