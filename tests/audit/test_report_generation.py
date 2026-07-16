# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""Tests for report generation edge cases."""

import os

from content_accessibility_utility_on_aws.api import audit_html_accessibility
from content_accessibility_utility_on_aws.utils.report_generator import generate_report

_HTML = "<html lang='en'><head><title>t</title></head><body><h1>Hi</h1></body></html>"


def test_generate_report_without_output_path_returns_data():
    """No output_path must return the report data, not crash on dirname(None).

    Regression: generate_report called os.path.dirname(output_path) with no
    None guard, so any caller that only wanted the in-memory report crashed.
    """
    report_data = {"summary": {"total_issues": 0}, "issues": []}
    for fmt in ("text", "json", "html"):
        result = generate_report(report_data, output_path=None, report_format=fmt)
        assert result is report_data


def test_audit_without_output_path_succeeds(tmp_path):
    """audit_html_accessibility(..., output_path=None) must not raise."""
    html_file = tmp_path / "page.html"
    html_file.write_text(_HTML, encoding="utf-8")

    result = audit_html_accessibility(str(html_file), options={})
    assert "issues" in result
    assert result.get("report")  # text report present in memory


def test_audit_with_output_path_still_writes(tmp_path):
    """The path-provided behavior is unchanged: the report file is written."""
    html_file = tmp_path / "page.html"
    html_file.write_text(_HTML, encoding="utf-8")
    out = tmp_path / "report.json"

    audit_html_accessibility(str(html_file), options={}, output_path=str(out))
    assert os.path.exists(out)
