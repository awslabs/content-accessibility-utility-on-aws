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

from content_accessibility_utility_on_aws.audit.base_check import AccessibilityCheck
from content_accessibility_utility_on_aws.utils.constants import MIN_TARGET_SIZE_PX
from content_accessibility_utility_on_aws.utils.css_dimensions import declared_dimension

# Interactive elements that act as pointer targets. Combined into one selector
# so soup.select returns each matching element once (no cross-selector dedup).
INTERACTIVE_SELECTOR = 'a[href], button, [role="button"], [role="link"]'


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
        # A single combined selector returns each matching element exactly once,
        # so no cross-selector deduplication is needed.
        for element in self.find_elements(INTERACTIVE_SELECTOR):
            # Inline links inside running text are exempt (inline exception).
            if element.name == "a" and self._is_inline_link(element):
                continue

            width = declared_dimension(element, "width")
            height = declared_dimension(element, "height")

            # No explicit dimensions declared: nothing reliable to assess in
            # static HTML, so do not flag (avoids false positives).
            if width is None and height is None:
                continue

            too_small = (width is not None and width < MIN_TARGET_SIZE_PX) or (
                height is not None and height < MIN_TARGET_SIZE_PX
            )

            text = self.get_element_text(element) or element.name
            if too_small:
                # Use "?" only for genuinely undeclared dimensions; a declared
                # 0px must render as "0", not be hidden by a falsy check.
                width_str = "?" if width is None else f"{width:g}"
                height_str = "?" if height is None else f"{height:g}"
                self.add_issue(
                    "target-size-too-small",
                    "2.5.8",
                    "minor",
                    element=element,
                    description=(
                        f"Interactive target '{text}' declares a size of "
                        f"{width_str}x{height_str} CSS px, below the "
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
