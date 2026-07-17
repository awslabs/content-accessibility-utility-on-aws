# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Remediation strategies for interactive / rendered accessibility issues.

These strategies remediate the issue types produced by the browser-backed
rendered audit (see ``agent/axe_adapter.py``). They follow the same contract as
every other strategy — ``(soup, issue, *args) -> Optional[str]`` operating on a
shared BeautifulSoup tree — so ``RemediationManager`` routes to them exactly
like the static strategies.

Unlike the static strategies, the *correctness* of these fixes is confirmed by
re-rendering and re-probing (the agent's ``verify`` tool / the deterministic
loop). A strategy here only has to make a well-formed, standards-based edit; the
verify step decides whether it actually closed the criterion, and the agent may
try an alternative if it did not.

Phase 0 implements focus-visible (WCAG 2.4.7). Contrast and name-role-value
strategies are added in later phases.
"""

from typing import Any, Dict, Optional

from bs4 import BeautifulSoup

from content_accessibility_utility_on_aws.remediate.helpers.selector_helper import (
    find_element_from_issue,
)
from content_accessibility_utility_on_aws.remediate.helpers.text_generation import (
    generate_short_text,
)
from content_accessibility_utility_on_aws.utils.logging_helper import setup_logger

logger = setup_logger(__name__)

# Required-state defaults per ARIA role, applied when a widget declares a role
# but omits the state attribute the role requires (WCAG 4.1.2).
_ROLE_REQUIRED_STATE = {
    "switch": ("aria-checked", "false"),
    "checkbox": ("aria-checked", "false"),
    "radio": ("aria-checked", "false"),
    "menuitemcheckbox": ("aria-checked", "false"),
    "menuitemradio": ("aria-checked", "false"),
    "tab": ("aria-selected", "false"),
    "option": ("aria-selected", "false"),
    "combobox": ("aria-expanded", "false"),
}

# Role -> the parent/container role ARIA requires it to live under, and the
# container's own role (used to wrap orphaned children; WCAG 4.1.2).
_ROLE_REQUIRED_PARENT = {
    "tab": "tablist",
    "option": "listbox",
    "menuitem": "menu",
    "menuitemcheckbox": "menu",
    "menuitemradio": "menu",
}

# Marker attribute so the injected style block is created once and reused, and
# so tests / re-runs can find it deterministically.
_FOCUS_STYLE_MARKER = "data-a11y-focus-visible"

# A standards-based, high-visibility focus indicator. Uses :focus-visible so it
# only shows for keyboard focus (not mouse clicks), with a :focus fallback for
# engines without :focus-visible. The 3px outline + offset comfortably meets
# WCAG 2.4.7 and the 2.4.13 focus-appearance guidance, and the outline color is
# chosen for contrast against typical light/dark backgrounds.
_FOCUS_CSS = (
    ":focus-visible{outline:3px solid #1a73e8 !important;"
    "outline-offset:2px !important;}"
    ":focus{outline:3px solid #1a73e8 !important;outline-offset:2px !important;}"
)


def _ensure_head(soup: BeautifulSoup):
    """Return the document ``<head>``, creating it (and ``<html>``) if absent.

    For a bare fragment (no ``<html>``) the existing top-level nodes are moved
    *inside* the new ``<html>`` rather than left as siblings of it, so the
    serialized document is well-formed rather than having content outside the
    root element.
    """
    head = soup.find("head")
    if head is not None:
        return head
    html = soup.find("html")
    if html is None:
        html = soup.new_tag("html")
        # Reparent existing top-level nodes under the new <html> so nothing is
        # left outside the root element.
        existing = [child for child in list(soup.children)]
        for child in existing:
            html.append(child.extract())
        soup.append(html)
    head = soup.new_tag("head")
    html.insert(0, head)
    return head


def remediate_focus_not_visible(
    soup: BeautifulSoup, issue: Dict[str, Any], *args
) -> Optional[str]:
    """Ensure interactive elements show a visible focus indicator (WCAG 2.4.7).

    The fix injects a single document-level ``:focus-visible`` style block. A
    global rule (rather than a per-element inline style) is used because focus
    styling is inherently a pseudo-class concern that cannot be expressed as an
    inline ``style`` attribute, and because one rule fixes every focusable
    element at once — the common case when a stylesheet did ``outline:none``.

    Args:
        soup: The BeautifulSoup document (mutated in place).
        issue: The accessibility issue (used for logging/traceability).
        *args: Optional BedrockClient (unused; deterministic fix).

    Returns:
        A message describing the remediation, or None if it could not be applied.
    """
    # Idempotent: if we already injected the focus style, report success without
    # adding a duplicate block (re-running an audit must not stack styles).
    existing = soup.find("style", attrs={_FOCUS_STYLE_MARKER: True})
    if existing is not None:
        return "Focus-visible indicator style already present"

    try:
        head = _ensure_head(soup)
    except Exception as e:  # pragma: no cover - malformed document
        logger.error("Could not locate/create <head> for focus style: %s", e)
        return None

    style_tag = soup.new_tag("style")
    style_tag[_FOCUS_STYLE_MARKER] = "true"
    style_tag.string = _FOCUS_CSS
    head.append(style_tag)

    # For traceability, note which element triggered the fix (best effort).
    target = find_element_from_issue(soup, issue)
    target_desc = f"<{target.name}>" if target is not None else "interactive elements"
    logger.debug("Injected focus-visible style prompted by %s", target_desc)

    return (
        "Added a visible :focus-visible outline style to the document so "
        "keyboard focus is perceptible (WCAG 2.4.7)"
    )


def _describe_from_context(element) -> Optional[str]:
    """Rule-based accessible name from an element's own signals (no model).

    Tries, in order: an icon class hint (e.g. ``icon-refresh`` -> "Refresh"),
    a title/value/placeholder attribute, and the nearest following text sibling
    (e.g. a toggle followed by a "Dark mode" label). Returns None if nothing
    usable is found.
    """
    # Icon class hint: the last hyphen segment of a class like "icon-export".
    for cls in element.get("class", []) or []:
        parts = str(cls).replace("_", "-").split("-")
        if len(parts) > 1 and parts[0] in ("icon", "btn", "ic", "fa"):
            word = parts[-1]
            if word.isalpha() and word not in ("btn", "icon"):
                return word.capitalize()
    for attr in ("title", "value", "placeholder", "alt"):
        val = element.get(attr)
        if isinstance(val, str) and val.strip():
            return val.strip()
    # Adjacent label text (common for toggles/switches: <span switch><span>Label).
    sib = element.find_next_sibling()
    if sib is not None:
        text = sib.get_text(strip=True) if hasattr(sib, "get_text") else ""
        if text and len(text) <= 40:
            return text
    return None


def remediate_missing_accessible_name(
    soup: BeautifulSoup, issue: Dict[str, Any], *args
) -> Optional[str]:
    """Give an interactive element an accessible name (WCAG 4.1.2).

    Custom widgets (``role="button"``, toggles, icon buttons) and controls with
    no text child have no accessible name, so assistive tech announces nothing.
    Adds an ``aria-label`` authored by the model from the element's context
    where available, falling back to a rule-based label from the element's own
    signals (icon class, title, adjacent text). Never overwrites an existing
    accessible name.
    """
    bedrock_client = args[0] if args else None

    el = find_element_from_issue(soup, issue)
    if el is None:
        return None
    # Respect an existing programmatic name.
    if el.get("aria-label") or el.get("aria-labelledby"):
        return "Element already has an accessible name; no change needed"
    # For text-content controls (buttons/links/custom-role widgets), visible
    # text IS the accessible name. For form controls (input/select/textarea) it
    # is NOT — a <select>'s option text or an <input>'s value does not name the
    # control — so those still need an aria-label even with inner text.
    _text_named = el.name not in ("select", "input", "textarea")
    if _text_named and el.get_text(strip=True):
        return "Element already has an accessible name; no change needed"

    role = el.get("role") or el.name
    parent = el.find_parent(["div", "section", "nav", "header", "form", "li"])
    surrounding = parent.get_text(separator=" ", strip=True)[:200] if parent else ""

    label = generate_short_text(
        bedrock_client,
        instruction=(
            f"Write a short accessible name (2-5 words) for this interactive "
            f"'{role}' control so a screen-reader user knows what it does. No "
            f"quotes or the word 'button'."
        ),
        context=(
            f"Element: <{el.name} role='{el.get('role','')}'>\n"
            f"Surrounding text: {surrounding}"
        ),
        purpose="accessible_name_generation",
        max_words=6,
    )
    if not label:
        label = _describe_from_context(el)
    if not label:
        return None

    el["aria-label"] = label
    return f"Added aria-label '{label}' to <{el.name}> (WCAG 4.1.2)"


def remediate_missing_aria_state(
    soup: BeautifulSoup, issue: Dict[str, Any], *args
) -> Optional[str]:
    """Add the ARIA state attribute a widget's role requires (WCAG 4.1.2).

    e.g. ``role="switch"``/``"checkbox"`` need ``aria-checked``; ``role="tab"``
    needs ``aria-selected``. Sets the neutral default (``false``); the app's JS
    should keep it in sync, but a present-and-default state is announced
    correctly, whereas a missing one is not.
    """
    el = find_element_from_issue(soup, issue)
    if el is None:
        return None
    role = (el.get("role") or "").lower()
    spec = _ROLE_REQUIRED_STATE.get(role)
    if not spec:
        return None
    attr, default = spec
    if el.get(attr) is not None:
        return f"<{el.name}> already declares {attr}; no change needed"
    # Reflect the visual 'on'/'active' class into the initial state when present.
    classes = " ".join(el.get("class", []) or []).lower()
    if attr in ("aria-checked", "aria-selected") and (
        "on" in classes.split() or "active" in classes.split() or "checked" in classes
    ):
        default = "true"
    el[attr] = default
    return f"Added {attr}='{default}' to role='{role}' widget (WCAG 4.1.2)"


def remediate_invalid_aria_structure(
    soup: BeautifulSoup, issue: Dict[str, Any], *args
) -> Optional[str]:
    """Establish the required parent role for an ARIA widget (WCAG 4.1.2).

    e.g. ``role="tab"`` must be owned by a ``role="tablist"``. If the element's
    container lacks the required role, set it on the nearest common parent so
    the relationship the role assumes actually exists.
    """
    el = find_element_from_issue(soup, issue)
    if el is None:
        return None
    role = (el.get("role") or "").lower()
    required_parent = _ROLE_REQUIRED_PARENT.get(role)
    if not required_parent:
        return None
    parent = el.parent
    if parent is None or not hasattr(parent, "get"):
        return None
    if (parent.get("role") or "").lower() == required_parent:
        return f"Parent already has role='{required_parent}'; no change needed"
    parent["role"] = required_parent
    return f"Set parent role='{required_parent}' for role='{role}' (WCAG 4.1.2)"
