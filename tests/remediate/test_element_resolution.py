# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Phase 4 — element resolution and issue-type normalization unit tests.

These directly cover the bugs fixed in code review: resolving an element from
the auditor's recorded location.path (the canonical mechanism), the href
fallback for when DOM mutation invalidates the path, and hyphen/underscore
issue-type normalization.
"""

from bs4 import BeautifulSoup

from content_accessibility_utility_on_aws.remediate.helpers.selector_helper import (
    find_element_from_issue,
)
from content_accessibility_utility_on_aws.remediate.remediation_manager import (
    RemediationManager,
)
from tests.conftest import make_issue


def test_resolves_by_path_with_document_token_stripped():
    soup = BeautifulSoup("<html><body><div><a href='/a'>x</a></div></body></html>", "html.parser")
    issue = make_issue("generic-link-text", path="html > body > div > a", element="a")
    el = find_element_from_issue(soup, issue)
    assert el is not None and el.name == "a"


def test_path_disambiguates_class_bearing_siblings():
    # Regression: two sibling <div class="card"> produce the same class-only
    # path, so the recorded path must carry :nth-of-type to resolve the right
    # descendant (not silently the first matching one).
    from content_accessibility_utility_on_aws.audit.auditor import AccessibilityAuditor

    html = (
        "<html><body>"
        "<div class='card'><a href='/a'>first</a></div>"
        "<div class='card'><a href='/b'></a></div>"
        "</body></html>"
    )
    soup = BeautifulSoup(html, "html.parser")
    auditor = AccessibilityAuditor.__new__(AccessibilityAuditor)
    target = soup.find_all("a")[1]  # the empty link in the second card
    path = AccessibilityAuditor._get_element_path(auditor, target)
    assert ":nth-of-type(2)" in path

    resolved = find_element_from_issue(soup, {"location": {"path": path}, "type": "x"})
    assert resolved is target


def test_resolves_correct_element_among_many_via_nth_of_type():
    soup = BeautifulSoup(
        "<html><body><p><a href='/1'>one</a><a href='/2'>two</a></p></body></html>",
        "html.parser",
    )
    issue = make_issue(
        "generic-link-text", path="html > body > p > a:nth-of-type(2)", element="a"
    )
    el = find_element_from_issue(soup, issue)
    assert el is not None
    assert el.get("href") == "/2"


def test_href_fallback_when_path_does_not_resolve():
    soup = BeautifulSoup("<html><body><div><a href='/target'>x</a></div></body></html>", "html.parser")
    # A stale path (element moved) but the recorded href still locates it.
    issue = make_issue(
        "generic-link-text", path="html > body > section > a", element="a", href="/target"
    )
    el = find_element_from_issue(soup, issue)
    assert el is not None
    assert el.get("href") == "/target"


def test_returns_none_when_unresolvable():
    soup = BeautifulSoup("<html><body><p>no links</p></body></html>", "html.parser")
    issue = make_issue("generic-link-text", path="html > body > a", element="a")
    assert find_element_from_issue(soup, issue) is None


def test_normalize_issue_type_underscores_to_hyphens():
    assert RemediationManager._normalize_issue_type("generic_link_text") == "generic-link-text"
    assert RemediationManager._normalize_issue_type("target-size-too-small") == "target-size-too-small"
    assert RemediationManager._normalize_issue_type(None) is None


def test_underscored_issue_type_resolves_to_a_strategy():
    soup = BeautifulSoup("<html><body></body></html>", "html.parser")
    mgr = RemediationManager(soup, options={"disable_ai": True})
    normalized = mgr._normalize_issue_type("generic_link_text")
    assert normalized in mgr.remediation_strategies
