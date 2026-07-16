# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Browser-backed tests (require Chromium via Playwright).

Run with: ``pytest -m rendered`` after ``pip install -e .[rendered]`` and
``playwright install chromium``. Skipped in the default suite.
"""

import pytest

from tests.rendered.conftest import FOCUS_FAIL_HTML

pytestmark = pytest.mark.rendered


def test_probe_detects_missing_focus_indicator(browser_probe):
    result = browser_probe.render_and_probe(FOCUS_FAIL_HTML)
    button = [f for f in result.focus_findings if f.selector == "button#go"]
    assert button, "focus probe should report the button"
    assert button[0].has_visible_indicator is False


def test_verify_closes_the_loop(browser_probe):
    # Before the fix, 2.4.7 fails for the button.
    assert browser_probe.verify(FOCUS_FAIL_HTML, "button#go", "2.4.7").passed is False

    # Apply the same fix the strategy produces and re-verify -> passes.
    fixed = FOCUS_FAIL_HTML.replace(
        "outline:none",
        "outline:none}button:focus-visible{outline:3px solid #1a73e8;outline-offset:2px",
    )
    assert browser_probe.verify(fixed, "button#go", "2.4.7").passed is True


def test_rendered_auditor_emits_canonical_issue(browser_probe):
    from content_accessibility_utility_on_aws.agent.rendered_auditor import (
        RenderedAuditor,
    )

    issues = RenderedAuditor(browser_probe).audit_html(FOCUS_FAIL_HTML, page_number=1)
    focus = [i for i in issues if i["type"] == "focus-not-visible"]
    assert focus, "rendered auditor should emit focus-not-visible"
    assert focus[0]["location"]["path"] == "button#go"
    assert focus[0]["wcag_criterion"] == "2.4.7"


def test_deterministic_loop_end_to_end(browser_probe):
    from content_accessibility_utility_on_aws.agent.deterministic_loop import (
        run_deterministic,
    )

    out = run_deterministic(browser_probe, FOCUS_FAIL_HTML)
    assert {"selector": "button#go", "criterion": "2.4.7"} in out["resolved"]
    assert "data-a11y-focus-visible" in out["html"]
    # After remediation, a fresh probe should find no focus-visible failure.
    result = browser_probe.render_and_probe(out["html"])
    remaining = [
        f for f in result.focus_findings
        if f.selector == "button#go" and not f.has_visible_indicator
    ]
    assert remaining == []


def test_rendered_option_is_additive_in_audit_api(tmp_path, browser_probe):
    """audit_html_accessibility with rendered=True adds the 2.4.7 issue; without it, none."""
    from content_accessibility_utility_on_aws.audit.api import audit_html_accessibility

    html_file = tmp_path / "page.html"
    html_file.write_text(FOCUS_FAIL_HTML, encoding="utf-8")
    # An output_path is supplied because the report generator requires one (the
    # real CLI always passes it); this test isolates the rendered-vs-static
    # behavior, not report generation.
    static_out = tmp_path / "static_report.json"
    rendered_out = tmp_path / "rendered_report.json"

    static = audit_html_accessibility(
        str(html_file), options={}, output_path=str(static_out)
    )
    static_types = {i["type"] for i in static["issues"]}
    assert "focus-not-visible" not in static_types  # static pass cannot see it

    rendered = audit_html_accessibility(
        str(html_file), options={"rendered": True}, output_path=str(rendered_out)
    )
    rendered_types = {i["type"] for i in rendered["issues"]}
    assert "focus-not-visible" in rendered_types  # rendered pass adds it


def test_rendered_multipage_ids_unique_and_file_stamped(tmp_path, browser_probe):
    """Multi-page: rendered issues get unique ids and their source file stamped."""
    from content_accessibility_utility_on_aws.audit.api import audit_html_accessibility

    # Two pages that are NOT named page-N.html, so page-number matching can't
    # save us — the file_path/file_name stamping must carry the identity.
    (tmp_path / "alpha.html").write_text(FOCUS_FAIL_HTML, encoding="utf-8")
    (tmp_path / "beta.html").write_text(FOCUS_FAIL_HTML, encoding="utf-8")
    out_report = tmp_path / "report.json"

    result = audit_html_accessibility(
        str(tmp_path), options={"rendered": True}, output_path=str(out_report)
    )
    focus = [i for i in result["issues"] if i["type"] == "focus-not-visible"]
    assert len(focus) == 2  # one per page

    # Ids are unique across pages (regression: they used to both be rendered-issue-1).
    ids = [i["id"] for i in focus]
    assert len(set(ids)) == len(ids)

    # Each rendered issue carries a resolvable source file (needed for
    # multi-page remediation matching and for the CSV/HTML report).
    file_names = {i["location"].get("file_name") for i in focus}
    assert file_names == {"alpha.html", "beta.html"}
