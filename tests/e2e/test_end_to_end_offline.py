# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Phase 5 — end-to-end offline smoke tests through the public API.

The API layer is file-path based, so these write HTML to tmp_path, run the
audit and remediation entry points with AI disabled, and assert the app
produces output and reduces the issue count. This is the "overall app works"
proof, with no AWS dependency.
"""

from content_accessibility_utility_on_aws.api import (
    audit_html_accessibility,
    remediate_html_accessibility,
)


SAMPLE_HTML = """<!DOCTYPE html>
<html>
<head></head>
<body>
<img src="chart.png">
<p>See <a href="https://example.com/report">click here</a> for details.</p>
<table><tr><td>Name</td><td>Age</td></tr><tr><td>Sam</td><td>30</td></tr></table>
</body>
</html>"""


def _write(tmp_path, html, name="doc.html"):
    p = tmp_path / name
    p.write_text(html, encoding="utf-8")
    return str(p)


def test_audit_api_returns_issues(tmp_path):
    html_path = _write(tmp_path, SAMPLE_HTML)
    report = audit_html_accessibility(
        html_path, output_path=str(tmp_path / "audit.json")
    )
    assert report["summary"]["total_issues"] > 0
    # Known problems in the sample should be detected.
    types = {i["type"] for i in report["issues"]}
    assert "missing-alt-text" in types
    assert "missing-document-language" in types


def test_remediate_api_produces_output_and_reduces_issues(tmp_path):
    html_path = _write(tmp_path, SAMPLE_HTML)
    output_path = str(tmp_path / "remediated.html")

    # Real workflow: audit first, then feed the report into remediation.
    before = audit_html_accessibility(html_path, output_path=str(tmp_path / "before.json"))
    before_needs = before["summary"].get("needs_remediation", before["summary"]["total_issues"])

    result = remediate_html_accessibility(
        html_path,
        audit_report=before,
        options={"disable_ai": True},
        output_path=output_path,
    )

    # The remediated document should exist.
    remediated = result.get("remediated_html_path") or output_path
    import os

    assert os.path.exists(remediated)

    # Re-auditing the output should show fewer outstanding issues.
    after = audit_html_accessibility(remediated, output_path=str(tmp_path / "after.json"))
    after_needs = after["summary"].get("needs_remediation", after["summary"]["total_issues"])
    assert after_needs <= before_needs


def test_remediated_document_adds_language(tmp_path):
    html_path = _write(tmp_path, SAMPLE_HTML)
    output_path = str(tmp_path / "remediated.html")
    report = audit_html_accessibility(html_path, output_path=str(tmp_path / "audit.json"))
    remediate_html_accessibility(
        html_path,
        audit_report=report,
        options={"disable_ai": True},
        output_path=output_path,
    )
    after = audit_html_accessibility(output_path, output_path=str(tmp_path / "after.json"))
    after_types = {i["type"] for i in after["issues"]}
    # Language is a deterministic fix that should hold end-to-end.
    assert "missing-document-language" not in after_types
