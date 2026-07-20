# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the trigger Lambda's prefix routing (no AWS needed).

Run: python3 -m pytest deployment/trigger_lambda/test_routing.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from handler import _route  # noqa: E402


def test_pdf_upload_routes_to_convert():
    assert _route("pdf/report.pdf")[0] == "convert"


def test_non_pdf_under_pdf_prefix_skipped():
    assert _route("pdf/notes.txt")[0] is None


def test_single_html_routes_to_audit():
    assert _route("html/page.html")[0] == "audit"
    assert _route("html/page.htm")[0] == "audit"


def test_zip_routes_to_audit():
    assert _route("html/site.zip")[0] == "audit"


def test_bundle_manifest_routes_to_audit():
    assert _route("html/report/manifest.json")[0] == "audit"


def test_bundle_assets_are_skipped():
    # These are the converted bundle's own objects — must NOT each trigger audit.
    assert _route("html/report/document.html")[0] is None
    assert _route("html/report/images/fig1.png")[0] is None
    assert _route("html/report/css/style.css")[0] is None
    assert _route("html/report/page-1.html")[0] is None


def test_output_prefix_not_triggered():
    assert _route("accessible/report/document.html")[0] is None


def test_unsupported_html_object_skipped():
    assert _route("html/readme.txt")[0] is None


def test_deeply_nested_manifest_still_audits():
    # Only basename == manifest.json matters within a bundle dir.
    assert _route("html/a/b/manifest.json")[0] == "audit"
    assert _route("html/a/b/document.html")[0] is None
