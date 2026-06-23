# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Target size accessibility checks (WCAG 2.2).

This module checks interactive controls against WCAG 2.2 Success Criterion
2.5.8 Target Size (Minimum), which requires pointer targets to be at least
24 by 24 CSS pixels unless an exception applies.

Note on scope: documents produced by this tool are static HTML converted from
PDFs. To avoid false positives, this check only flags interactive elements that
declare an *explicit* size below the 24x24 CSS pixel minimum (via width/height
attributes or inline CSS). Links rendered inline within a block of text are
exempt under the criterion's "inline" exception and are not flagged.
"""

import re
from typing import Optional

from content_accessibility_utility_on_aws.audit.base_check import AccessibilityCheck

# WCAG 2.2 minimum target dimension in CSS pixels.
MIN_TARGET_SIZE_PX = 24

# Interactive elements that act as pointer targets.
INTERACTIVE_SELECTORS = ["a[href]", "button", '[role="button"]', '[role="link"]']


class TargetSizeCheck(AccessibilityCheck):
    """Check that interactive targets meet the 24x24 CSS px minimum (WCAG 2.5.8)."""

    def check(self) -> None:
        """
        Check interactive elements for an explicit size below the minimum.

        Issues:
            - target-size-too-small: An interactive element declares a width or
              height below 24 CSS pixels.
            - compliant-target-size: An interactive element declares a size that
              meets the minimum (compliance success).
        """
        seen = set()
        for selector in INTERACTIVE_SELECTORS:
            for element in self.find_elements(selector):
                # An element may match several selectors; only evaluate it once.
                element_id = id(element)
                if element_id in seen:
                    continue
                seen.add(element_id)

                # Inline links inside running text are exempt (inline exception).
                if element.name == "a" and self._is_inline_link(element):
                    continue

                width = self._declared_dimension(element, "width")
                height = self._declared_dimension(element, "height")

                # No explicit dimensions declared: nothing reliable to assess in
                # static HTML, so do not flag (avoids false positives).
                if width is None and height is None:
                    continue

                too_small = (width is not None and width < MIN_TARGET_SIZE_PX) or (
                    height is not None and height < MIN_TARGET_SIZE_PX
                )

                text = self.get_element_text(element) or element.name
                if too_small:
                    self.add_issue(
                        "target-size-too-small",
                        "2.5.8",
                        "minor",
                        element=element,
                        description=(
                            f"Interactive target '{text}' declares a size of "
                            f"{width or '?'}x{height or '?'} CSS px, below the "
                            f"{MIN_TARGET_SIZE_PX}x{MIN_TARGET_SIZE_PX} px minimum"
                        ),
                    )
                else:
                    self.add_issue(
                        "compliant-target-size",
                        "2.5.8",
                        "info",
                        element=element,
                        description=(
                            f"Interactive target '{text}' meets the minimum "
                            f"target size"
                        ),
                        status="compliant",
                    )

    def _is_inline_link(self, element) -> bool:
        """
        Determine whether a link is rendered inline within a block of text.

        Links that sit inside a paragraph or similar text container alongside
        other text are exempt from 2.5.8 under the "inline" exception.
        """
        text_parents = ("p", "li", "span", "td", "th", "dd", "dt", "figcaption")
        parent = element.parent
        if parent is None or parent.name not in text_parents:
            return False

        # Inline only if there is sibling text beyond the link's own text.
        parent_text = parent.get_text(strip=True)
        link_text = element.get_text(strip=True)
        return len(parent_text) > len(link_text)

    def _declared_dimension(self, element, dimension: str) -> Optional[float]:
        """
        Extract an explicitly declared pixel dimension for an element.

        Looks at the inline ``style`` first (width/height/min-width/min-height),
        then the legacy HTML ``width``/``height`` attribute. Returns the value in
        CSS pixels, or None if no explicit pixel value is declared.
        """
        style = self.get_attribute(element, "style") or ""
        # Prefer min-<dimension> when present, since it sets the floor.
        for prop in (f"min-{dimension}", dimension):
            match = re.search(rf"\b{prop}\s*:\s*([0-9.]+)px", style, re.IGNORECASE)
            if match:
                try:
                    return float(match.group(1))
                except ValueError:
                    pass

        attr_value = self.get_attribute(element, dimension)
        if attr_value:
            match = re.match(r"^\s*([0-9.]+)\s*(px)?\s*$", str(attr_value))
            if match:
                try:
                    return float(match.group(1))
                except ValueError:
                    pass

        return None
