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
from content_accessibility_utility_on_aws.utils.logging_helper import setup_logger

logger = setup_logger(__name__)

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
