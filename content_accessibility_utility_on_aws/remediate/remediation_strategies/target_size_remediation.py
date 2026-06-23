# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Target size accessibility remediation strategies (WCAG 2.2).

Remediates WCAG 2.2 Success Criterion 2.5.8 Target Size (Minimum) by ensuring
interactive targets render at least 24 by 24 CSS pixels. The fix enforces a
minimum size via inline CSS (``min-width``/``min-height``) and removes any
explicit smaller width/height that would otherwise shrink the target.
"""

import re
from typing import Dict, Any, Optional

from bs4 import BeautifulSoup

# WCAG 2.2 minimum target dimension in CSS pixels.
MIN_TARGET_SIZE_PX = 24


def _find_target(soup: BeautifulSoup, issue: Dict[str, Any]):
    """Locate the interactive element referenced by the issue."""
    location = issue.get("location") or {}
    element_str = issue.get("element", "")

    # Prefer matching by href when the element is a link.
    href_match = re.search(r'href="([^"]*)"', element_str)
    if href_match:
        candidates = soup.find_all("a", href=href_match.group(1))
        if candidates:
            return candidates[0]

    # Fall back to the element name recorded on the issue (e.g. "button").
    element_name = location.get("element_name") or (
        element_str if element_str in ("button", "a") else None
    )
    if element_name:
        candidates = soup.find_all(element_name)
        if len(candidates) == 1:
            return candidates[0]

    return None


def _strip_undersized_dimensions(style: str) -> str:
    """Remove explicit width/height declarations below the minimum size."""

    def keep(declaration: str) -> bool:
        match = re.match(
            r"\s*(width|height)\s*:\s*([0-9.]+)px\s*$", declaration, re.IGNORECASE
        )
        if not match:
            return True
        try:
            return float(match.group(2)) >= MIN_TARGET_SIZE_PX
        except ValueError:
            return True

    declarations = [d for d in style.split(";") if d.strip()]
    return "; ".join(d.strip() for d in declarations if keep(d))


def remediate_target_size_too_small(
    soup: BeautifulSoup, issue: Dict[str, Any], *args
) -> Optional[str]:
    """
    Remediate an undersized interactive target by enforcing the minimum size.

    Args:
        soup: The BeautifulSoup object representing the HTML document
        issue: The accessibility issue to remediate
        *args: Optional BedrockClient (unused; this is a deterministic fix)

    Returns:
        A message describing the remediation, or None if no remediation was performed
    """
    element = _find_target(soup, issue)
    if element is None:
        return None

    # Drop any explicit undersized width/height, then enforce the minimum.
    style = element.get("style", "")
    style = _strip_undersized_dimensions(style)

    declarations = [
        f"min-width: {MIN_TARGET_SIZE_PX}px",
        f"min-height: {MIN_TARGET_SIZE_PX}px",
    ]
    # A box model is required for min-width/min-height to take effect on inline
    # elements such as links; only add one if the element does not set display.
    if not re.search(r"\bdisplay\s*:", style, re.IGNORECASE):
        declarations.append("display: inline-block")

    enforced = "; ".join(declarations)
    style = f"{style.rstrip(';').strip()}; {enforced}" if style.strip() else enforced
    element["style"] = style.strip("; ").strip()

    # Drop legacy HTML width/height attributes that could override the CSS.
    for attr in ("width", "height"):
        if element.has_attr(attr):
            del element[attr]

    return (
        f"Enforced {MIN_TARGET_SIZE_PX}x{MIN_TARGET_SIZE_PX} px minimum target size "
        f"on <{element.name}>"
    )
