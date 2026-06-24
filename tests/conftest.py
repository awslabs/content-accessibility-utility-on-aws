# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Shared pytest fixtures and helpers for the test suite.

These helpers keep the offline core tests free of AWS: the auditor runs on HTML
strings and the remediation manager runs with ``disable_ai=True`` (or a fake
Bedrock client), so nothing here constructs a real boto3 client.
"""

from typing import Any, Dict, List, Optional

import pytest
from bs4 import BeautifulSoup

from content_accessibility_utility_on_aws.audit.auditor import AccessibilityAuditor


def audit_html(html: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Run the full accessibility audit on an HTML string and return the report.

    Args:
        html: The HTML document to audit.
        options: Optional auditor options (e.g. severity_threshold).

    Returns:
        The audit report dict (with "issues", "summary", etc.).
    """
    return AccessibilityAuditor(html_content=html, options=options).audit()


def issues_of_type(report: Dict[str, Any], issue_type: str) -> List[Dict[str, Any]]:
    """Return all issues in a report matching the given type."""
    return [i for i in report["issues"] if i.get("type") == issue_type]


def has_issue_type(report: Dict[str, Any], issue_type: str) -> bool:
    """Whether the report contains at least one issue of the given type."""
    return bool(issues_of_type(report, issue_type))


def make_issue(
    issue_type: str,
    *,
    path: Optional[str] = None,
    element: str = "",
    href: Optional[str] = None,
    extra_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Build an audit-shaped issue dict for driving remediation strategies directly.

    Mirrors what ``AccessibilityAuditor._add_issue`` stores: ``element`` is the
    bare tag name, the CSS selector lives under ``location.path`` (prefixed with
    the BeautifulSoup ``[document]`` root token), and anchor hrefs are recoverable
    from ``context``. Tests use this so they exercise the same issue shape the
    real pipeline produces — the shape that the ``_find_target`` bug hinged on.

    Args:
        issue_type: The issue type (e.g. "generic-link-text").
        path: CSS selector path (without the leading "[document] > ").
        element: The recorded element string (normally the tag name).
        href: Optional anchor href, stored under context.attributes.href.
        extra_context: Additional context fields to merge.

    Returns:
        An issue dict suitable for passing to a remediation strategy.
    """
    context: Dict[str, Any] = {}
    if href is not None:
        context["attributes"] = {"href": href}
        context["html_snippet"] = f'<a href="{href}">link</a>'
    if extra_context:
        context.update(extra_context)

    location: Dict[str, Any] = {"page_number": None}
    if path is not None:
        location["path"] = f"[document] > {path}"

    return {
        "type": issue_type,
        "element": element,
        "location": location,
        "context": context,
    }


class FakeBedrockClient:
    """
    A stand-in for BedrockClient that returns canned text without calling AWS.

    Used to exercise the model-backed remediation paths deterministically. The
    ``responses`` map is keyed by the ``purpose`` argument the strategies pass,
    so a test can assert which generation path ran. Records all calls for
    inspection.
    """

    def __init__(self, responses: Optional[Dict[str, str]] = None):
        self.responses = responses or {}
        self.model_id = "fake-model"
        self.profile = None
        self.calls: List[Dict[str, Any]] = []

    def generate_text(
        self, prompt: str, purpose: str = "general", max_tokens: int = 2000, **kwargs
    ) -> str:
        self.calls.append({"prompt": prompt, "purpose": purpose})
        return self.responses.get(purpose, "Generated text")

    def generate_alt_text_for_image(
        self, image_path: str, prompt: str, max_tokens: int = 2000
    ) -> str:
        self.calls.append({"image_path": image_path, "prompt": prompt})
        return self.responses.get("alt_text_generation", "Generated alt text")


@pytest.fixture
def fake_bedrock_client():
    """Factory fixture: build a FakeBedrockClient with optional canned responses."""

    def _make(responses: Optional[Dict[str, str]] = None) -> FakeBedrockClient:
        return FakeBedrockClient(responses)

    return _make


@pytest.fixture
def soup_of():
    """Factory fixture: parse an HTML string into BeautifulSoup."""

    def _make(html: str) -> BeautifulSoup:
        return BeautifulSoup(html, "html.parser")

    return _make
