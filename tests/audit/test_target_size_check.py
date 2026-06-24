# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Phase 1 — WCAG 2.2 Target Size (2.5.8) audit check tests.

Covers the conservative detection rules: explicit undersized targets are
flagged, inline links in running text are exempt, targets with no declared size
are not flagged, and a declared 0px renders as "0" (not hidden by a falsy check).
"""

from tests.conftest import audit_html, has_issue_type, issues_of_type


def test_undersized_button_is_flagged():
    report = audit_html(
        "<html><body><div>"
        "<button style='width:10px;height:10px'>x</button>"
        "</div></body></html>"
    )
    assert has_issue_type(report, "target-size-too-small")
    assert issues_of_type(report, "target-size-too-small")[0]["wcag_criterion"] == "2.5.8"


def test_undersized_via_html_attribute_is_flagged():
    report = audit_html(
        "<html><body><div><a href='/x' width='12' height='12'>icon</a></div></body></html>"
    )
    assert has_issue_type(report, "target-size-too-small")


def test_adequately_sized_target_is_compliant():
    report = audit_html(
        "<html><body><div>"
        "<button style='min-width:40px;min-height:40px'>OK</button>"
        "</div></body></html>"
    )
    assert has_issue_type(report, "compliant-target-size")
    assert not has_issue_type(report, "target-size-too-small")


def test_inline_link_in_running_text_is_exempt():
    report = audit_html(
        "<html><body><p>Read the "
        "<a href='/x' style='width:5px;height:5px'>full report</a> now.</p></body></html>"
    )
    # Inline exception: a link inside a sentence is not flagged even if small.
    assert not has_issue_type(report, "target-size-too-small")


def test_target_with_no_declared_size_is_not_flagged():
    report = audit_html(
        "<html><body><div><button>No size declared</button></div></body></html>"
    )
    # Avoid false positives: with no explicit size we cannot assess it.
    assert not has_issue_type(report, "target-size-too-small")


def test_zero_px_renders_as_zero_in_description():
    report = audit_html(
        "<html><body><div><button style='width:0px'>z</button></div></body></html>"
    )
    issues = issues_of_type(report, "target-size-too-small")
    assert issues
    # A declared 0px must show as "0", not "?" (the falsy-zero bug).
    assert "0x" in issues[0]["description"]
    assert "?x?" not in issues[0]["description"]
