# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Tests for the computed-contrast capability (WCAG 1.4.3):
  - shared color-contrast math (utils/color_contrast.py),
  - the deterministic remediate_computed_contrast strategy,
  - AgentSession.author_css_rule (the agent's real-CSS-rule tool).
All browser-free.
"""

from bs4 import BeautifulSoup

from content_accessibility_utility_on_aws.utils.color_contrast import (
    AA_NORMAL_TEXT,
    adjust_for_contrast,
    contrast_ratio,
    parse_color,
    relative_luminance,
    to_hex,
)
from content_accessibility_utility_on_aws.remediate.remediation_strategies.interactive_remediation import (
    remediate_computed_contrast,
)
from content_accessibility_utility_on_aws.agent.session import AgentSession


# --- color math --------------------------------------------------------------

def test_parse_color_hex_and_rgb():
    assert parse_color("#fff") == (255, 255, 255)
    assert parse_color("#000000") == (0, 0, 0)
    assert parse_color("rgb(18, 52, 86)") == (18, 52, 86)
    assert parse_color("rgba(255,0,0,0.5)") == (255, 0, 0)
    assert parse_color("transparent") is None
    assert parse_color("rebeccapurple") is None


def test_contrast_ratio_extremes():
    assert round(contrast_ratio((0, 0, 0), (255, 255, 255)), 1) == 21.0
    assert contrast_ratio((255, 255, 255), (255, 255, 255)) == 1.0


def test_relative_luminance_monotonic():
    assert relative_luminance((0, 0, 0)) < relative_luminance((128, 128, 128))
    assert relative_luminance((128, 128, 128)) < relative_luminance((255, 255, 255))


def test_adjust_for_contrast_light_background():
    fg, bg = (153, 153, 153), (255, 255, 255)  # #999 on white ~ 2.85:1
    assert contrast_ratio(fg, bg) < AA_NORMAL_TEXT
    fixed = adjust_for_contrast(fg, bg)
    assert fixed is not None
    assert contrast_ratio(fixed, bg) >= AA_NORMAL_TEXT


def test_adjust_for_contrast_dark_background():
    fg, bg = (120, 120, 120), (17, 17, 17)
    fixed = adjust_for_contrast(fg, bg)
    assert fixed is not None
    assert contrast_ratio(fixed, bg) >= AA_NORMAL_TEXT


def test_adjust_returns_same_when_already_compliant():
    fg, bg = (0, 0, 0), (255, 255, 255)
    assert adjust_for_contrast(fg, bg) == fg


# --- deterministic strategy --------------------------------------------------

def _issue(sel):
    return {"type": "computed-contrast-insufficient", "location": {"path": sel}, "element": ""}


def test_strategy_nudges_inline_color():
    soup = BeautifulSoup(
        '<html><body><p id="t" style="color:#999;background-color:#fff">hi</p>'
        "</body></html>",
        "html.parser",
    )
    msg = remediate_computed_contrast(soup, _issue("#t"))
    assert msg and "1.4.3" in msg
    style = soup.find(id="t").get("style")
    new_color = parse_color(
        [d.split(":", 1)[1] for d in style.split(";") if d.strip().startswith("color:")][0]
    )
    assert contrast_ratio(new_color, (255, 255, 255)) >= AA_NORMAL_TEXT


def test_strategy_uses_measured_context_colors():
    soup = BeautifulSoup('<html><body><span id="k">x</span></body></html>', "html.parser")
    issue = _issue("#k")
    issue["context"] = {"foreground_color": "#aaaaaa", "background_color": "#ffffff"}
    msg = remediate_computed_contrast(soup, issue)
    assert msg and "color:" in msg


def test_strategy_noop_when_already_compliant():
    soup = BeautifulSoup(
        '<html><body><p id="t" style="color:#000;background-color:#fff">hi</p></body></html>',
        "html.parser",
    )
    msg = remediate_computed_contrast(soup, _issue("#t"))
    assert "already meets" in msg


def test_strategy_returns_none_without_parseable_color():
    soup = BeautifulSoup('<html><body><p id="t">hi</p></body></html>', "html.parser")
    # No inline color and no measured context -> cannot act deterministically.
    assert remediate_computed_contrast(soup, _issue("#t")) is None


# --- author_css_rule ---------------------------------------------------------

def _session(html):
    return AgentSession(probe=None, html=html)


def test_author_css_rule_injects_rule():
    s = _session("<html><head></head><body><span class='kpi'>x</span></body></html>")
    msg = s.author_css_rule(".kpi", "color:#111 !important; background-color:#fff !important")
    assert ".kpi{" in msg
    assert "data-a11y-agent-css" in s.html
    assert ".kpi{color:#111 !important; background-color:#fff !important;}" in s.html


def test_author_css_rule_accumulates_in_one_block():
    s = _session("<html><head></head><body></body></html>")
    s.author_css_rule(".a", "color:#111")
    s.author_css_rule(".b", "color:#222")
    soup = BeautifulSoup(s.html, "html.parser")
    blocks = soup.find_all("style", attrs={"data-a11y-agent-css": True})
    assert len(blocks) == 1  # single managed block
    assert ".a{" in blocks[0].string and ".b{" in blocks[0].string


def test_author_css_rule_creates_head_when_missing():
    s = _session("<span class='k'>x</span>")
    s.author_css_rule(".k", "color:#111")
    assert "data-a11y-agent-css" in s.html


def test_author_css_rule_rejects_markup_injection():
    s = _session("<html><head></head><body></body></html>")
    msg = s.author_css_rule(".x", "color:red}</style><script>alert(1)</script>")
    assert "Rejected" in msg
    assert "<script>" not in s.html


def test_author_css_rule_requires_both_args():
    s = _session("<html><head></head><body></body></html>")
    assert "needs both" in s.author_css_rule("", "color:red")
    assert "needs both" in s.author_css_rule(".x", "")
