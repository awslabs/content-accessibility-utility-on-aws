# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Audit accuracy: generic and decorative alt text, severity of passing items,
crashed checks reported as ``check-error``, and WCAG 2.2's obsolete 4.1.1.

Offline: the auditor runs on HTML strings, no mocking of AWS needed.
"""

import os

import pytest

from content_accessibility_utility_on_aws.agent.axe_adapter import _issue_from_parts
from content_accessibility_utility_on_aws.audit import auditor as auditor_module
from content_accessibility_utility_on_aws.audit.auditor import AccessibilityAuditor
from content_accessibility_utility_on_aws.audit.checks.image_checks import (
    generic_alt_reason,
)
from content_accessibility_utility_on_aws.audit.standards import (
    DEFAULT_WCAG_VERSION,
    criterion_for_version,
    relabel_issue_for_version,
)
from tests.conftest import audit_html, has_issue_type, issues_of_type

FIXTURE = os.path.join(
    os.path.dirname(__file__), "..", "fixtures", "inaccessible", "report.html"
)


def _img_report(img_html):
    return audit_html(f"<html><body>{img_html}</body></html>")


# --- generic alt -------------------------------------------------------------


@pytest.mark.parametrize(
    "img",
    [
        '<img src="x.png" alt="chart">',
        '<img src="x.png" alt="Chart">',
        '<img src="x.png" alt="graph">',
        '<img src="x.png" alt="IMG_1234.jpg">',
        '<img src="x.png" alt="DSC00042.JPG">',
        '<img src="x.png" alt="IMG_1234">',
        '<img src="images/trend_chart.png" alt="trend_chart.png">',
        '<img src="images/trend_chart.png" alt="trend_chart">',
        '<img src="https://cdn.example.com/a/q3-revenue.webp?v=2" alt="q3-revenue">',
    ],
)
def test_generic_alt_is_flagged(img):
    report = _img_report(img)
    assert has_issue_type(report, "generic-alt-text"), img
    assert not has_issue_type(report, "compliant-alt-text")


@pytest.mark.parametrize(
    "alt",
    [
        "Bar chart of quarterly sales",
        "Company logo for Example Corp",
        "Photo of the team at the 2024 offsite",
    ],
)
def test_descriptive_alt_mentioning_kind_is_compliant(alt):
    report = _img_report(f'<img src="x.png" alt="{alt}">')
    assert has_issue_type(report, "compliant-alt-text")
    assert not has_issue_type(report, "generic-alt-text")


def test_generic_alt_reason_explains_why():
    assert generic_alt_reason("chart") == "generic word"
    assert generic_alt_reason("IMG_1234.jpg") == "file name"
    assert (
        generic_alt_reason("sales-map", "img/sales-map.svg")
        == "same as image file name"
    )
    assert generic_alt_reason("Map of sales by region", "img/sales-map.svg") == ""


# --- decorative --------------------------------------------------------------


@pytest.mark.parametrize(
    "img",
    [
        '<img src="divider.png" alt="">',
        '<img src="divider.png" alt="  ">',
        '<img src="divider.png" alt="" role="presentation">',
        '<img src="divider.png" role="presentation">',
        '<img src="divider.png" role="none">',
        '<img src="divider.png" aria-hidden="true">',
    ],
)
def test_decorative_images_are_compliant(img):
    report = _img_report(img)
    assert has_issue_type(report, "compliant-decorative-image"), img
    assert not has_issue_type(report, "empty-alt-text")
    assert not has_issue_type(report, "missing-alt-text")


def test_missing_alt_without_decorative_marker_still_flagged():
    report = _img_report('<img src="x.png" aria-hidden="false">')
    assert has_issue_type(report, "missing-alt-text")


# --- passing items are info --------------------------------------------------


def test_compliant_items_are_info_severity():
    report = audit_html(
        "<html lang='en'><head><title>Sales</title></head><body><main>"
        "<h1>Sales</h1><img src='x.png' alt='Bar chart of quarterly sales'>"
        "<img src='d.png' alt=''></main></body></html>"
    )
    compliant = [i for i in report["issues"] if i["remediation_status"] == "compliant"]
    assert compliant
    assert {i["severity"] for i in compliant} == {"info"}
    alt = issues_of_type(report, "compliant-alt-text")[0]
    assert alt["severity"] == "info"  # was "critical"


# --- check errors ------------------------------------------------------------


def test_crashed_check_is_reported_not_skipped(monkeypatch):
    def boom(self):
        raise ValueError("bad selector")

    monkeypatch.setattr(auditor_module.TargetSizeCheck, "check", boom)
    report = audit_html(
        "<html><body><img src='x.png'></body></html>",
        options={"severity_threshold": "critical"},
    )

    errors = issues_of_type(report, "check-error")
    assert len(errors) == 1
    err = errors[0]
    assert err["context"]["check"] == "TargetSizeCheck"
    assert err["context"]["exception"] == "ValueError"
    assert "bad selector" in err["description"]
    # Not routed to remediation, and not hidden by the severity threshold.
    assert err["remediation_status"] == "check_error"
    assert report["summary"]["check_errors"] == 1
    # Other checks still ran.
    assert has_issue_type(report, "missing-alt-text")


def test_clean_run_reports_zero_check_errors():
    report = audit_html("<html><body><p>Hi</p></body></html>")
    assert report["summary"]["check_errors"] == 0


# --- WCAG 2.2: 4.1.1 is obsolete ---------------------------------------------


def test_default_target_is_wcag_22():
    assert DEFAULT_WCAG_VERSION == "2.2"
    report = audit_html("<html><body><p>Hi</p></body></html>")
    assert report["summary"]["wcag_version"] == "2.2"


def test_criterion_mapping_by_version():
    assert criterion_for_version("4.1.1", "2.2") == "4.1.2"
    assert criterion_for_version("4.1.1", "2.1") == "4.1.1"
    assert criterion_for_version("1.1.1", "2.2") == "1.1.1"
    assert criterion_for_version("4.1.1", "9.9") == "4.1.2"  # unknown -> default


def test_static_issue_under_411_is_relabelled_for_22():
    auditor = AccessibilityAuditor(html_content="<html><body></body></html>")
    auditor._add_issue("duplicate-id", "4.1.1", "major", description="dup")
    issue = auditor.issues[-1]
    assert issue["wcag_criterion"] == "4.1.2"
    assert issue["criterion_name"] == "Name, Role, Value"
    assert issue["original_wcag_criterion"] == "4.1.1"


def test_static_issue_keeps_411_for_21():
    auditor = AccessibilityAuditor(
        html_content="<html><body></body></html>", options={"wcag_version": "2.1"}
    )
    auditor._add_issue("duplicate-id", "4.1.1", "major", description="dup")
    issue = auditor.issues[-1]
    assert issue["wcag_criterion"] == "4.1.1"
    assert "original_wcag_criterion" not in issue


def test_rendered_duplicate_id_relabelled_for_22():
    issue = _issue_from_parts(
        issue_type="duplicate-id",
        wcag="4.1.1",
        severity="major",
        selector="#x",
        element_tag="input",
        description="dup",
    )
    relabel_issue_for_version(issue, "2.2")
    assert issue["wcag_criterion"] == "4.1.2"
    assert issue["original_wcag_criterion"] == "4.1.1"


# --- fixture recall ----------------------------------------------------------


def test_inaccessible_fixture_alt_recall():
    report = AccessibilityAuditor(html_path=FIXTURE).audit()
    by_src = {}
    for issue in report["issues"]:
        if issue["wcag_criterion"] != "1.1.1" or issue["type"].startswith(
            "missing-figure"
        ):
            continue
        attrs = (issue.get("context") or {}).get("attributes") or {}
        src = attrs.get("src") or ""
        by_src.setdefault(os.path.basename(src), set()).add(issue["type"])

    assert "missing-alt-text" in by_src.get("logo.png", set())
    assert "missing-alt-text" in by_src.get("throughput_chart.png", set())
    # alt="chart" was reported as compliant (severity "critical") before.
    assert by_src.get("trend_chart.png") == {"generic-alt-text"}
    # alt="" is the decorative marker: not flagged.
    assert by_src.get("region_chart.png") == {"compliant-decorative-image"}
    assert report["summary"]["check_errors"] == 0


def test_text_report_shows_check_error_count(monkeypatch, tmp_path):
    from content_accessibility_utility_on_aws.utils.report_generator import (
        generate_text_report,
    )

    def boom(self):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(auditor_module.TargetSizeCheck, "check", boom)
    report = audit_html("<html><body><p>Hi</p></body></html>")
    out = tmp_path / "audit.txt"
    generate_text_report(report, str(out), "accessibility")
    text = out.read_text(encoding="utf-8")
    assert "Check errors (criteria not evaluated): 1" in text
    assert "check-error" in text
