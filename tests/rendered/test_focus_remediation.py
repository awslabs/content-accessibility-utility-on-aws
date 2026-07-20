# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""Browser-free tests for the focus-visible remediation strategy + routing."""

from bs4 import BeautifulSoup

from content_accessibility_utility_on_aws.remediate.remediation_manager import (
    RemediationManager,
)
from content_accessibility_utility_on_aws.remediate.remediation_strategies.interactive_remediation import (
    remediate_focus_not_visible,
)


def _issue(selector="button#go"):
    return {
        "id": "i1",
        "type": "focus-not-visible",
        "location": {"path": selector},
        "element": "",
    }


def test_strategy_injects_focus_style():
    html = "<html><head><title>t</title></head><body><button id='go'>Go</button></body></html>"
    soup = BeautifulSoup(html, "html.parser")
    msg = remediate_focus_not_visible(soup, _issue())
    assert msg is not None
    style = soup.find("style", attrs={"data-a11y-focus-visible": True})
    assert style is not None
    assert ":focus-visible" in style.string


def test_strategy_is_idempotent():
    html = "<html><head><title>t</title></head><body><button id='go'>Go</button></body></html>"
    soup = BeautifulSoup(html, "html.parser")
    remediate_focus_not_visible(soup, _issue())
    remediate_focus_not_visible(soup, _issue())
    styles = soup.find_all("style", attrs={"data-a11y-focus-visible": True})
    assert len(styles) == 1


def test_strategy_creates_head_when_missing():
    html = "<button id='go'>Go</button>"
    soup = BeautifulSoup(html, "html.parser")
    msg = remediate_focus_not_visible(soup, _issue())
    assert msg is not None
    assert soup.find("style", attrs={"data-a11y-focus-visible": True}) is not None


def test_fragment_is_reparented_under_html():
    """Existing fragment content must move inside <html>, not sit outside it."""
    soup = BeautifulSoup("<button id='go'>Go</button>", "html.parser")
    remediate_focus_not_visible(soup, _issue())
    html_tag = soup.find("html")
    assert html_tag is not None
    # The button is inside <html>, and the style is inside <head>.
    assert html_tag.find("button") is not None
    assert soup.find("head").find("style", attrs={"data-a11y-focus-visible": True})
    # Nothing is left as an element sibling of <html> at the top level.
    top_level_elements = [c.name for c in soup.children if getattr(c, "name", None)]
    assert top_level_elements == ["html"]


def test_remediation_manager_routes_focus_not_visible():
    """The manager's registry routes the new issue type to the strategy."""
    html = "<html><head><title>t</title></head><body><button id='go'>Go</button></body></html>"
    soup = BeautifulSoup(html, "html.parser")
    manager = RemediationManager(soup, {"disable_ai": True})
    assert "focus-not-visible" in manager.remediation_strategies
    assert "missing-focus-indicator" in manager.remediation_strategies
    msg = manager.remediate_issue(_issue())
    assert msg is not None
    assert soup.find("style", attrs={"data-a11y-focus-visible": True}) is not None
