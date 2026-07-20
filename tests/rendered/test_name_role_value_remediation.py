# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Browser-free tests for the name-role-value (WCAG 4.1.2) remediation strategies
and the widened axe rule map. These cover the custom-widget failures a complex
interactive dashboard produces (accessible name, required ARIA state/structure).
"""

from bs4 import BeautifulSoup

from content_accessibility_utility_on_aws.agent.axe_adapter import AXE_RULE_MAP
from content_accessibility_utility_on_aws.remediate.remediation_strategies.interactive_remediation import (
    remediate_invalid_aria_structure,
    remediate_missing_accessible_name,
    remediate_missing_aria_state,
)


def _issue(itype, path):
    return {"type": itype, "element": "", "location": {"path": f"[document] > {path}"}, "context": {}}


# --- adapter coverage ---

def test_axe_map_covers_custom_widget_name_rules():
    for rule in ("aria-command-name", "aria-toggle-field-name", "select-name",
                 "aria-input-field-name"):
        assert AXE_RULE_MAP[rule]["type"] == "missing-accessible-name"
        assert AXE_RULE_MAP[rule]["wcag"] == "4.1.2"


def test_axe_map_covers_aria_structure_rules():
    for rule in ("aria-required-parent", "aria-required-children"):
        assert AXE_RULE_MAP[rule]["type"] == "invalid-aria-structure"


# --- accessible name ---

def test_names_icon_button_from_class_hint():
    soup = BeautifulSoup(
        '<html><body><span class="icon-refresh" role="button" tabindex="0"></span></body></html>',
        "html.parser",
    )
    remediate_missing_accessible_name(soup, _issue("missing-accessible-name", "html > body > span"))
    assert soup.find("span").get("aria-label") == "Refresh"


class _FakeClient:
    """Canned model response for the accessible-name authoring path."""

    model_id = "fake"
    profile = None

    def generate_text(self, prompt, purpose="general", max_tokens=2000, **kw):
        return "Date range"


def test_select_option_text_is_not_treated_as_a_name():
    # Regression: a <select>'s option text is NOT an accessible name, so the
    # strategy must NOT short-circuit on get_text() (it used to). With a model
    # available it authors an aria-label.
    soup = BeautifulSoup(
        "<html><body><select><option>Last 7 days</option></select></body></html>",
        "html.parser",
    )
    msg = remediate_missing_accessible_name(
        soup, _issue("missing-accessible-name", "html > body > select"), _FakeClient()
    )
    assert soup.find("select").get("aria-label") == "Date range", msg


def test_contextless_control_defers_when_no_model():
    # Honest fallback behavior: with no model and no derivable signal, the
    # strategy declines rather than inventing a wrong name.
    soup = BeautifulSoup(
        "<html><body><select><option>Last 7 days</option></select></body></html>",
        "html.parser",
    )
    msg = remediate_missing_accessible_name(
        soup, _issue("missing-accessible-name", "html > body > select")
    )
    assert msg is None
    assert soup.find("select").get("aria-label") is None


def test_does_not_overwrite_existing_aria_label():
    soup = BeautifulSoup(
        '<html><body><button aria-label="Save">x</button></body></html>', "html.parser"
    )
    msg = remediate_missing_accessible_name(soup, _issue("missing-accessible-name", "html > body > button"))
    assert "no change needed" in msg
    assert soup.find("button").get("aria-label") == "Save"


# --- required state ---

def test_adds_aria_checked_to_switch():
    soup = BeautifulSoup(
        '<html><body><span class="toggle on" role="switch" tabindex="0"></span></body></html>',
        "html.parser",
    )
    remediate_missing_aria_state(soup, _issue("missing-aria-state", "html > body > span"))
    # 'on' class -> initial state true.
    assert soup.find("span").get("aria-checked") == "true"


def test_adds_aria_selected_to_tab():
    soup = BeautifulSoup(
        '<html><body><div role="tab" tabindex="0">Overview</div></body></html>', "html.parser"
    )
    remediate_missing_aria_state(soup, _issue("missing-aria-state", "html > body > div"))
    assert soup.find("div").get("aria-selected") == "false"


# --- required structure ---

def test_sets_tablist_parent_for_tab():
    soup = BeautifulSoup(
        '<html><body><div class="tabs"><div role="tab" tabindex="0">A</div></div></body></html>',
        "html.parser",
    )
    remediate_invalid_aria_structure(
        soup, _issue("invalid-aria-structure", "html > body > div.tabs > div")
    )
    assert soup.find("div", class_="tabs").get("role") == "tablist"
