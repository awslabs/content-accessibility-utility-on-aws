# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Tests for disambiguating duplicate link text (WCAG 2.4.9).

Same-text/different-URL links have no mechanical fix, so this is the agent's
"semantic authoring" territory. These tests cover the rule-based fallback (no
model) and the model-backed path (fake client), plus the already-resolved case.
"""

from bs4 import BeautifulSoup

from content_accessibility_utility_on_aws.audit.context_collector import ContextCollector
from content_accessibility_utility_on_aws.remediate.remediation_strategies.link_remediation import (
    remediate_duplicate_link_text,
)


def _issue(link):
    return {
        "type": "duplicate-link-text-different-url",
        "element": "a",
        "location": {"path": ""},
        "context": ContextCollector(link).collect(),
    }


def test_fallback_appends_path_hint_to_first_of_duplicates():
    html = ('<html><body><p>See <a href="/docs/api">Documentation</a> and '
            '<a href="/docs/cli">Documentation</a>.</p></body></html>')
    soup = BeautifulSoup(html, "html.parser")
    first = soup.find_all("a")[0]
    msg = remediate_duplicate_link_text(soup, _issue(first))  # no client -> fallback
    assert msg and "Documentation" in msg
    assert first.get_text(strip=True) != "Documentation"  # now distinct


def test_fallback_distinguishes_same_text_absolute_urls():
    # Prefer the distinguishing path segment; fall back to domain only if the
    # path does not differentiate. Here /x vs /y makes the links distinct.
    html = ('<html><body><p><a href="https://a.example.com/x">Report</a> '
            '<a href="https://b.example.com/y">Report</a></p></body></html>')
    soup = BeautifulSoup(html, "html.parser")
    first = soup.find_all("a")[0]
    remediate_duplicate_link_text(soup, _issue(first))
    t = first.get_text(strip=True)
    assert t != "Report"  # disambiguated
    assert "x" in t  # path segment appended


def test_fallback_avoids_leaving_same_domain_links_identical():
    # Two "here" links to the same host, different paths: the domain alone would
    # leave them identical ("here (x.com)" x2); the path must distinguish them.
    html = ('<html><body><p><a href="https://x.com/alpha">here</a> '
            '<a href="https://x.com/beta">here</a></p></body></html>')
    soup = BeautifulSoup(html, "html.parser")
    links = soup.find_all("a")
    remediate_duplicate_link_text(soup, _issue(links[0]))
    remediate_duplicate_link_text(soup, _issue(links[1]))
    texts = [a.get_text(strip=True) for a in soup.find_all("a")]
    assert texts[0] != texts[1], f"links still identical: {texts}"


def test_already_unique_link_reports_no_change():
    html = ('<html><body><p><a href="/a">Alpha</a> '
            '<a href="/b">Beta</a></p></body></html>')
    soup = BeautifulSoup(html, "html.parser")
    link = soup.find("a")
    msg = remediate_duplicate_link_text(soup, _issue(link))
    assert msg is not None
    assert "already unique" in msg.lower()
    assert link.get_text(strip=True) == "Alpha"  # untouched


class _FakeClient:
    """Returns canned descriptive text for the model-backed path."""

    model_id = "fake"
    profile = None

    def generate_text(self, prompt, purpose="general", max_tokens=2000, **kw):
        return "View the API reference"


def test_model_backed_authors_descriptive_text():
    html = ('<html><body><p>See <a href="/docs/api">click here</a> and '
            '<a href="/docs/cli">click here</a>.</p></body></html>')
    soup = BeautifulSoup(html, "html.parser")
    first = soup.find_all("a")[0]
    msg = remediate_duplicate_link_text(soup, _issue(first), _FakeClient())
    assert first.get_text(strip=True) == "View the API reference"
    assert "click here" not in first.get_text(strip=True).lower()
