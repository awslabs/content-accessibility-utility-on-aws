# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Phase 1 — audit check tests (offline, no mocking).

Each test feeds a known-bad or known-good HTML string through the full auditor
and asserts that the expected issue type fires with the right WCAG criterion,
or that a compliant result is recorded. These lock in detection behavior across
the check classes registered in the auditor.
"""

from tests.conftest import audit_html, has_issue_type, issues_of_type


def criterion_for(report, issue_type):
    """Return the wcag_criterion of the first issue of the given type."""
    matches = issues_of_type(report, issue_type)
    assert matches, f"expected an issue of type {issue_type!r}"
    return matches[0]["wcag_criterion"]


# --- Images (1.1.1) ---------------------------------------------------------


def test_image_missing_alt_is_flagged():
    report = audit_html("<html><body><img src='x.png'></body></html>")
    assert has_issue_type(report, "missing-alt-text")
    assert criterion_for(report, "missing-alt-text") == "1.1.1"


def test_image_empty_alt_non_decorative_is_flagged():
    report = audit_html("<html><body><img src='x.png' alt=''></body></html>")
    assert has_issue_type(report, "empty-alt-text")


def test_image_decorative_empty_alt_is_compliant():
    report = audit_html(
        "<html><body><img src='x.png' alt='' role='presentation'></body></html>"
    )
    assert has_issue_type(report, "compliant-decorative-image")
    assert not has_issue_type(report, "empty-alt-text")


def test_image_generic_alt_is_flagged():
    report = audit_html("<html><body><img src='x.png' alt='image'></body></html>")
    assert has_issue_type(report, "generic-alt-text")


def test_image_descriptive_alt_is_compliant():
    report = audit_html(
        "<html><body><img src='x.png' alt='Bar chart of quarterly sales'></body></html>"
    )
    assert has_issue_type(report, "compliant-alt-text")


# --- Headings (1.3.1, 2.4.6) ------------------------------------------------


def test_no_headings_is_flagged():
    report = audit_html("<html><body><p>Just text</p></body></html>")
    assert has_issue_type(report, "no-headings")


def test_missing_h1_is_flagged():
    report = audit_html("<html><body><h2>Subsection</h2></body></html>")
    assert has_issue_type(report, "no-h1")


def test_skipped_heading_level_is_flagged():
    report = audit_html(
        "<html><body><h1>Title</h1><h3>Skipped past h2</h3></body></html>"
    )
    assert has_issue_type(report, "skipped-heading-level")


def test_proper_heading_hierarchy_is_compliant():
    report = audit_html(
        "<html><body><h1>Title</h1><h2>Section</h2></body></html>"
    )
    assert has_issue_type(report, "compliant-heading-hierarchy")
    assert not has_issue_type(report, "skipped-heading-level")


def test_empty_heading_is_flagged():
    report = audit_html("<html><body><h1></h1></body></html>")
    assert has_issue_type(report, "empty-heading")


def test_generic_heading_is_flagged():
    report = audit_html("<html><body><h1>Heading</h1></body></html>")
    assert has_issue_type(report, "generic-heading")


# --- Document title (2.4.2) -------------------------------------------------


def test_missing_title_is_flagged():
    report = audit_html("<html><head></head><body><h1>Doc</h1></body></html>")
    assert has_issue_type(report, "missing-title")


def test_present_title_is_compliant():
    report = audit_html(
        "<html><head><title>Annual Report</title></head><body><h1>Doc</h1></body></html>"
    )
    assert has_issue_type(report, "compliant-document-title")


# --- Document language (3.1.1) ----------------------------------------------


def test_missing_lang_is_flagged():
    report = audit_html("<html><body><p>Text</p></body></html>")
    assert has_issue_type(report, "missing-document-language")


def test_present_lang_is_compliant():
    report = audit_html("<html lang='en'><body><p>Text</p></body></html>")
    assert has_issue_type(report, "compliant-document-language")


# --- Links (2.4.4) ----------------------------------------------------------


def test_empty_link_text_is_flagged():
    report = audit_html("<html><body><a href='/x'></a></body></html>")
    assert has_issue_type(report, "empty-link-text")


def test_generic_link_text_is_flagged():
    report = audit_html(
        "<html><body><p>See <a href='/x'>click here</a></p></body></html>"
    )
    assert has_issue_type(report, "generic-link-text")


def test_descriptive_link_text_is_compliant():
    report = audit_html(
        "<html><body><p>See the <a href='/x'>annual sales report</a></p></body></html>"
    )
    assert has_issue_type(report, "compliant-link-text")


# --- Tables (1.3.1) ---------------------------------------------------------


def test_table_missing_headers_is_flagged():
    report = audit_html(
        "<html><body><table><tr><td>a</td><td>b</td></tr>"
        "<tr><td>c</td><td>d</td></tr></table></body></html>"
    )
    assert has_issue_type(report, "table-missing-headers")


def test_table_header_missing_scope_is_flagged():
    report = audit_html(
        "<html><body><table><tr><th>Name</th><th>Age</th></tr>"
        "<tr><td>Sam</td><td>30</td></tr></table></body></html>"
    )
    assert has_issue_type(report, "table-missing-scope")


# --- Forms (1.3.1, 3.3.2) ---------------------------------------------------


def test_form_input_missing_label_is_flagged():
    report = audit_html(
        "<html><body><form><input type='text' name='email'></form></body></html>"
    )
    # The form label check emits "form-control-missing-label".
    assert has_issue_type(report, "form-control-missing-label")


# --- Structure / landmarks --------------------------------------------------


def test_missing_main_landmark_is_flagged():
    report = audit_html("<html><body><p>No landmarks here</p></body></html>")
    assert has_issue_type(report, "missing-main-landmark")


def test_main_landmark_present_is_compliant():
    report = audit_html("<html><body><main><p>Content</p></main></body></html>")
    assert has_issue_type(report, "compliant-main-landmark")


# --- Report shape -----------------------------------------------------------


def test_report_has_expected_structure():
    report = audit_html("<html lang='en'><body><img src='x.png'></body></html>")
    assert "summary" in report
    assert "issues" in report
    assert report["summary"]["total_issues"] == len(report["issues"])
    for issue in report["issues"]:
        assert "type" in issue
        assert "wcag_criterion" in issue
        assert "remediation_status" in issue
