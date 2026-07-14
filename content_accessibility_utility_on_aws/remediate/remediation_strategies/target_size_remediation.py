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

from content_accessibility_utility_on_aws.utils.constants import MIN_TARGET_SIZE_PX
from content_accessibility_utility_on_aws.utils.css_dimensions import (
    strip_undersized_dimensions,
)
from content_accessibility_utility_on_aws.remediate.helpers.selector_helper import (
    find_element_from_issue,
)


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
    element = find_element_from_issue(soup, issue)
    if element is None:
        return None

    # Drop any explicit undersized width/height (including !important ones that
    # would otherwise override the enforced minimum), then enforce the minimum.
    style = strip_undersized_dimensions(element.get("style", ""), MIN_TARGET_SIZE_PX)

    declarations = [
        f"min-width: {MIN_TARGET_SIZE_PX}px",
        f"min-height: {MIN_TARGET_SIZE_PX}px",
    ]
    # A box model is required for min-width/min-height to take effect on inline
    # elements such as links; add one if the element sets no display, or if it
    # explicitly sets ``display: none`` (which has no rendered box at all, so
    # the enforced minimum would otherwise be meaningless).
    display_match = re.search(r"\bdisplay\s*:\s*([a-z-]+)", style, re.IGNORECASE)
    if display_match is None:
        declarations.append("display: inline-block")
    elif display_match.group(1).lower() == "none":
        # Drop the ``display: none`` declaration so the target can render.
        style = re.sub(
            r"\bdisplay\s*:\s*none\s*(!important)?\s*;?",
            "",
            style,
            flags=re.IGNORECASE,
        ).strip("; ").strip()
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
