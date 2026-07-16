# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""Browser-free tests for the axe adapter and rendered de-dup logic."""

from content_accessibility_utility_on_aws.agent.axe_adapter import (
    AxeAdapter,
    rendered_issue_types,
)
from content_accessibility_utility_on_aws.agent.rendered_auditor import RenderedAuditor

# Keys the canonical issue dict must carry so it flows through the existing
# report + remediation routing unchanged (mirrors _add_issue output).
CANONICAL_KEYS = {
    "id",
    "type",
    "wcag_criterion",
    "criterion_name",
    "criterion_level",
    "severity",
    "element",
    "description",
    "context",
    "location",
    "remediation_status",
    "remediation_source",
    "remediation_date",
}


def test_focus_finding_maps_to_canonical_issue(focus_fail_probe_result):
    issues = AxeAdapter(page_number=2).to_issues(focus_fail_probe_result)
    assert len(issues) == 1
    issue = issues[0]
    assert CANONICAL_KEYS <= set(issue)
    assert issue["type"] == "focus-not-visible"
    assert issue["wcag_criterion"] == "2.4.7"
    assert issue["criterion_name"] == "Focus Visible"
    assert issue["location"]["path"] == "button#go"
    assert issue["location"]["page_number"] == 2
    assert issue["remediation_status"] == "needs_remediation"


def test_compliant_focus_findings_are_not_emitted(focus_fail_probe_result):
    # Flip the finding to "has a visible indicator" -> no issue.
    focus_fail_probe_result.focus_findings[0].has_visible_indicator = True
    issues = AxeAdapter().to_issues(focus_fail_probe_result)
    assert issues == []


def test_axe_contrast_violation_maps_to_issue(contrast_probe_result):
    issues = AxeAdapter().to_issues(contrast_probe_result)
    assert len(issues) == 1
    issue = issues[0]
    assert issue["type"] == "computed-contrast-insufficient"
    assert issue["wcag_criterion"] == "1.4.3"
    assert issue["location"]["path"] == "p.lo"


def test_rendered_issue_types_include_focus_and_contrast():
    types = rendered_issue_types()
    assert "focus-not-visible" in types
    assert "computed-contrast-insufficient" in types


def test_dedupe_drops_static_contrast_superseded_by_rendered():
    static_issues = [
        {
            "type": "insufficient-color-contrast",
            "wcag_criterion": "1.4.3",
            "location": {"path": "p.lo"},
        },
        {
            "type": "missing-alt-text",
            "wcag_criterion": "1.1.1",
            "location": {"path": "img"},
        },
    ]
    rendered_issues = [
        {
            "type": "computed-contrast-insufficient",
            "wcag_criterion": "1.4.3",
            "location": {"path": "p.lo"},
        }
    ]
    kept = RenderedAuditor.dedupe(static_issues, rendered_issues)
    kept_types = {i["type"] for i in kept}
    # Static contrast on the same node/criterion is dropped; alt-text survives.
    assert "insufficient-color-contrast" not in kept_types
    assert "missing-alt-text" in kept_types


def test_dedupe_matches_across_document_prefixed_static_path():
    """Static paths carry a '[document] >' prefix; rendered/axe paths do not.

    Regression: without normalizing that prefix the keys never matched and no
    static issue was ever superseded.
    """
    static_issues = [
        {
            "type": "insufficient-color-contrast",
            "wcag_criterion": "1.4.3",
            "location": {"path": "[document] > html > body > p.lo"},
        }
    ]
    rendered_issues = [
        {
            "type": "computed-contrast-insufficient",
            "wcag_criterion": "1.4.3",
            "location": {"path": "html > body > p.lo"},
        }
    ]
    kept = RenderedAuditor.dedupe(static_issues, rendered_issues)
    assert not any(i["type"] == "insufficient-color-contrast" for i in kept)


def test_dedupe_keeps_static_contrast_on_different_node():
    static_issues = [
        {
            "type": "insufficient-color-contrast",
            "wcag_criterion": "1.4.3",
            "location": {"path": "p.other"},
        }
    ]
    rendered_issues = [
        {
            "type": "computed-contrast-insufficient",
            "wcag_criterion": "1.4.3",
            "location": {"path": "p.lo"},
        }
    ]
    kept = RenderedAuditor.dedupe(static_issues, rendered_issues)
    assert len(kept) == 1  # different node, not superseded
