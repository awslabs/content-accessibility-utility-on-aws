# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Tests for focus-order (#5, WCAG 2.4.3): the probe reports positive-tabindex
elements, the adapter emits focus-order-broken issues, and the remediation
neutralizes the positive tabindex. Browser-free.
"""

from bs4 import BeautifulSoup

from content_accessibility_utility_on_aws.agent.axe_adapter import (
    AxeAdapter,
    rendered_issue_types,
)
from content_accessibility_utility_on_aws.agent.browser_probe import (
    FocusOrderFinding,
    ProbeResult,
)
from content_accessibility_utility_on_aws.remediate.remediation_strategies.interactive_remediation import (
    remediate_focus_order,
)


def test_adapter_emits_focus_order_issue():
    pr = ProbeResult(
        focus_order_findings=[
            FocusOrderFinding(selector="button#a", html="<button>", tabindex=3)
        ]
    )
    issues = AxeAdapter().to_issues(pr)
    assert len(issues) == 1
    assert issues[0]["type"] == "focus-order-broken"
    assert issues[0]["wcag_criterion"] == "2.4.3"
    assert issues[0]["location"]["path"] == "button#a"


def test_focus_order_in_rendered_types():
    assert "focus-order-broken" in rendered_issue_types()


def _issue(sel):
    return {"type": "focus-order-broken", "location": {"path": sel}, "element": ""}


def test_remediate_neutralizes_positive_tabindex():
    soup = BeautifulSoup(
        '<html><body><button id="a" tabindex="5">X</button></body></html>', "html.parser"
    )
    msg = remediate_focus_order(soup, _issue("#a"))
    assert "0" in msg
    assert soup.find(id="a").get("tabindex") == "0"


def test_remediate_noop_on_zero_tabindex():
    soup = BeautifulSoup(
        '<html><body><button id="a" tabindex="0">X</button></body></html>', "html.parser"
    )
    msg = remediate_focus_order(soup, _issue("#a"))
    assert "no change needed" in msg
    assert soup.find(id="a").get("tabindex") == "0"


def test_remediate_noop_on_negative_tabindex():
    # tabindex="-1" (programmatically focusable, out of tab order) is legitimate.
    soup = BeautifulSoup(
        '<html><body><div id="a" tabindex="-1">X</div></body></html>', "html.parser"
    )
    msg = remediate_focus_order(soup, _issue("#a"))
    assert "no change needed" in msg
    assert soup.find(id="a").get("tabindex") == "-1"
