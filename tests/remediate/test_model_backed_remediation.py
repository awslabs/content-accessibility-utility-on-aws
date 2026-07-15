# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Phase 3 — model-backed remediation tests using a fake Bedrock client.

Verifies that the Tier 1 strategies use model output when a client is present
and fall back to deterministic rule-based behavior when it is absent — the
fallback-first contract — without any real AWS call.
"""

from bs4 import BeautifulSoup

from content_accessibility_utility_on_aws.remediate.remediation_strategies.heading_remediation import (
    remediate_empty_heading_content,
)
from content_accessibility_utility_on_aws.remediate.remediation_strategies.document_structure_remediation import (
    remediate_missing_document_title,
)
from content_accessibility_utility_on_aws.remediate.remediation_strategies.form_remediation import (
    remediate_missing_form_labels,
)
from content_accessibility_utility_on_aws.remediate.remediation_strategies.link_remediation import (
    remediate_generic_link_text,
)
from tests.conftest import make_issue


def test_heading_uses_model_output(fake_bedrock_client):
    client = fake_bedrock_client({"heading_generation": "Quarterly Revenue Growth"})
    soup = BeautifulSoup(
        "<html><body><h2 id='h'>123</h2><p>Revenue grew strongly this quarter.</p></body></html>",
        "html.parser",
    )
    issue = make_issue("empty-heading", path="html > body > h2", element="h2")
    remediate_empty_heading_content(soup, issue, client)
    assert soup.find("h2", id="h").get_text(strip=True) == "Quarterly Revenue Growth"


def test_heading_falls_back_without_client():
    soup = BeautifulSoup(
        "<html><body><h2 id='h'>123</h2><p>Revenue grew strongly this quarter.</p></body></html>",
        "html.parser",
    )
    issue = make_issue("empty-heading", path="html > body > h2", element="h2")
    # No client -> rule-based fallback still produces non-empty heading text.
    result = remediate_empty_heading_content(soup, issue, None)
    assert result is not None
    assert soup.find("h2", id="h").get_text(strip=True) != ""


def test_document_title_uses_model_output(fake_bedrock_client):
    client = fake_bedrock_client({"document_title_generation": "2024 Annual Financial Report"})
    soup = BeautifulSoup(
        "<html><head></head><body><p>This report covers fiscal year 2024 results.</p></body></html>",
        "html.parser",
    )
    remediate_missing_document_title(soup, make_issue("missing-page-title"), client)
    assert soup.find("title").get_text(strip=True) == "2024 Annual Financial Report"


def test_form_label_uses_model_output(fake_bedrock_client):
    client = fake_bedrock_client({"form_label_generation": "Email Address"})
    soup = BeautifulSoup(
        "<html><body><form><p>Enter your email</p><input id='f1'></form></body></html>",
        "html.parser",
    )
    issue = make_issue("missing-input-label", path="html > body > form > input", element="input")
    remediate_missing_form_labels(soup, issue, client)
    label = soup.find("label")
    assert label is not None
    assert label.get_text(strip=True) == "Email Address"


def test_link_text_uses_model_output(fake_bedrock_client):
    client = fake_bedrock_client({"link_text_generation": "View the annual report"})
    soup = BeautifulSoup(
        "<html><body><p>Download. <a href='https://ex.com/r'>click here</a></p></body></html>",
        "html.parser",
    )
    issue = make_issue(
        "generic-link-text", path="html > body > p > a", element="a", href="https://ex.com/r"
    )
    remediate_generic_link_text(soup, issue, client)
    assert soup.find("a").get_text(strip=True) == "View the annual report"


def test_link_text_falls_back_without_client():
    soup = BeautifulSoup(
        "<html><body><p>Download. <a href='https://ex.com/r'>click here</a></p></body></html>",
        "html.parser",
    )
    issue = make_issue(
        "generic-link-text", path="html > body > p > a", element="a", href="https://ex.com/r"
    )
    result = remediate_generic_link_text(soup, issue, None)
    assert result is not None
    assert soup.find("a").get_text(strip=True).lower() != "click here"


def test_model_called_with_expected_purpose(fake_bedrock_client):
    client = fake_bedrock_client({"heading_generation": "A Heading"})
    soup = BeautifulSoup(
        "<html><body><h2 id='h'>123</h2><p>Some section content here.</p></body></html>",
        "html.parser",
    )
    issue = make_issue("empty-heading", path="html > body > h2", element="h2")
    remediate_empty_heading_content(soup, issue, client)
    assert any(c.get("purpose") == "heading_generation" for c in client.calls)
