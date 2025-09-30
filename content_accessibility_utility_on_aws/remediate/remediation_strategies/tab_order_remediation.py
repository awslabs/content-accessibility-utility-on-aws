# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""Tab order remediation strategy.

This module provides algorithmic remediation for tab order issues (WCAG 2.4.3).
"""

from typing import Dict, List, Any, Optional, Tuple
from bs4 import BeautifulSoup, Tag
import re
from content_accessibility_utility_on_aws.utils.logging_helper import setup_logger

logger = setup_logger(__name__)


class TabOrderRemediation:
    """Algorithmic remediation for tab order issues."""

    # Interactive elements that should be in tab order
    INTERACTIVE_SELECTORS = [
        "a[href]",
        "button:not([disabled])",
        "input:not([disabled]):not([type='hidden'])",
        "select:not([disabled])",
        "textarea:not([disabled])",
        "area[href]",
    ]

    def __init__(
        self,
        html_content: str,
        issues: List[Dict[str, Any]],
        options: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize tab order remediation.

        Args:
            html_content: The HTML content to remediate
            issues: List of tab order issues from audit
            options: Remediation options
        """
        self.html_content = html_content
        self.soup = BeautifulSoup(html_content, "html.parser")
        self.issues = issues
        self.options = options or {}
        self.changes: List[Dict[str, Any]] = []

    def remediate(self) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Perform algorithmic tab order remediation.

        Returns:
            Tuple of (remediated HTML, list of changes made)
        """
        logger.info("Starting tab order remediation")

        # Step 1: Remove positive tabindex values
        self._remove_positive_tabindex()

        # Step 2: Remove unnecessary tabindex="0" from non-interactive elements
        self._remove_unnecessary_tabindex_zero()

        # Step 3: Attempt DOM reordering for visual order mismatches
        if self.options.get("reorder_dom_for_visual_order", True):
            self._reorder_dom_by_visual_position()

        # Step 4: Add tabindex="-1" where appropriate
        self._add_appropriate_negative_tabindex()

        logger.info(f"Tab order remediation complete. Made {len(self.changes)} changes")
        return str(self.soup), self.changes

    def _remove_positive_tabindex(self) -> None:
        """Remove all positive tabindex values."""
        elements = self.soup.find_all(
            lambda tag: tag.has_attr("tabindex") and self._is_positive_tabindex(tag)
        )

        for element in elements:
            old_value = element.get("tabindex")
            del element["tabindex"]

            self.changes.append(
                {
                    "type": "positive_tabindex_removed",
                    "element": self._get_element_identifier(element),
                    "element_type": element.name,
                    "old_value": old_value,
                    "new_value": None,
                    "reason": "Positive tabindex disrupts natural tab order",
                }
            )

            logger.debug(f"Removed tabindex='{old_value}' from {element.name}")

    def _remove_unnecessary_tabindex_zero(self) -> None:
        """Remove tabindex='0' from non-interactive elements."""
        # Find tab order issues that are about unnecessary tabindex zero
        unnecessary_tabindex_issues = [
            issue
            for issue in self.issues
            if issue.get("type") == "unnecessary-tabindex-zero"
        ]

        for issue in unnecessary_tabindex_issues:
            # Find the element based on the issue context
            element_id = issue.get("context", {}).get("element_id")
            element_name = issue.get("context", {}).get("element_name")

            if element_id:
                element = self.soup.find(id=element_id)
            else:
                # Try to find by path or other means
                element = self._find_element_from_issue(issue)

            if (
                element
                and element.has_attr("tabindex")
                and element.get("tabindex") == "0"
            ):
                del element["tabindex"]

                self.changes.append(
                    {
                        "type": "unnecessary_tabindex_zero_removed",
                        "element": self._get_element_identifier(element),
                        "element_type": element.name,
                        "old_value": "0",
                        "new_value": None,
                        "reason": "Non-interactive element does not need tabindex",
                    }
                )

                logger.debug(f"Removed unnecessary tabindex='0' from {element.name}")

    def _reorder_dom_by_visual_position(self) -> None:
        """
        Reorder DOM elements to match visual reading order.

        This is complex and only applied when we have clear visual position data.
        """
        # Find tab-order-mismatch issues
        mismatch_issues = [
            issue for issue in self.issues if issue.get("type") == "tab-order-mismatch"
        ]

        if not mismatch_issues:
            logger.debug("No tab order mismatches found, skipping DOM reordering")
            return

        # Get all interactive elements with position data
        interactive_elements = self._get_interactive_elements_with_position()

        if len(interactive_elements) < 2:
            logger.debug("Not enough elements with position data for reordering")
            return

        # Sort by visual position
        visual_order = self._sort_by_visual_position(interactive_elements)

        # Group by common parent to avoid breaking document structure
        grouped_by_parent = self._group_by_common_parent(visual_order)

        # Reorder within each group
        for parent, elements in grouped_by_parent.items():
            if len(elements) > 1:
                self._reorder_siblings(parent, elements)

    def _get_interactive_elements_with_position(self) -> List[Dict[str, Any]]:
        """Get all interactive elements that have position data."""
        interactive_elements = []

        for selector in self.INTERACTIVE_SELECTORS:
            elements = self.soup.select(selector)
            for idx, element in enumerate(elements):
                bbox_data = self._extract_bbox_data(element)
                if bbox_data:
                    interactive_elements.append(
                        {
                            "element": element,
                            "bbox": bbox_data,
                            "original_index": idx,
                        }
                    )

        return interactive_elements

    def _extract_bbox_data(self, element: Tag) -> Optional[Dict[str, float]]:
        """Extract bounding box data from element attributes."""
        # Check for BDA bounding box data
        if element.has_attr("data-bda-bbox"):
            try:
                bbox_str = element.get("data-bda-bbox")
                x, y, width, height = map(float, bbox_str.split(","))
                return {"x": x, "y": y, "width": width, "height": height}
            except (ValueError, AttributeError):
                pass

        # Check for individual coordinate attributes
        if all(element.has_attr(attr) for attr in ["data-x", "data-y"]):
            try:
                return {
                    "x": float(element.get("data-x")),
                    "y": float(element.get("data-y")),
                    "width": float(element.get("data-width", 0)),
                    "height": float(element.get("data-height", 0)),
                }
            except (ValueError, AttributeError):
                pass

        return None

    def _sort_by_visual_position(
        self, elements_with_position: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Sort elements by visual reading order (top-to-bottom, left-to-right)."""
        if not elements_with_position:
            return []

        # Group into rows
        rows = self._group_into_rows(elements_with_position, threshold=20.0)

        # Sort rows by Y position
        rows.sort(key=lambda row: row["y_min"])

        # Within each row, sort by X position
        sorted_elements = []
        for row in rows:
            row["elements"].sort(key=lambda el: el["bbox"]["x"])
            sorted_elements.extend(row["elements"])

        return sorted_elements

    def _group_into_rows(
        self, elements_with_position: List[Dict[str, Any]], threshold: float = 20.0
    ) -> List[Dict[str, Any]]:
        """Group elements into rows based on Y-coordinate proximity."""
        if not elements_with_position:
            return []

        rows = []

        for element_data in elements_with_position:
            y_pos = element_data["bbox"]["y"]

            # Find existing row this element belongs to
            found_row = False
            for row in rows:
                if abs(y_pos - row["y_min"]) <= threshold:
                    row["elements"].append(element_data)
                    row["y_min"] = min(row["y_min"], y_pos)
                    row["y_max"] = max(
                        row["y_max"], y_pos + element_data["bbox"].get("height", 0)
                    )
                    found_row = True
                    break

            # Create new row if needed
            if not found_row:
                rows.append(
                    {
                        "y_min": y_pos,
                        "y_max": y_pos + element_data["bbox"].get("height", 0),
                        "elements": [element_data],
                    }
                )

        return rows

    def _group_by_common_parent(
        self, elements: List[Dict[str, Any]]
    ) -> Dict[Tag, List[Dict[str, Any]]]:
        """Group elements by their immediate common parent."""
        grouped = {}

        for element_data in elements:
            element = element_data["element"]
            parent = element.parent

            if parent not in grouped:
                grouped[parent] = []
            grouped[parent].append(element_data)

        return grouped

    def _reorder_siblings(self, parent: Tag, elements: List[Dict[str, Any]]) -> None:
        """
        Reorder sibling elements within their parent.

        Args:
            parent: The parent element
            elements: List of element data in desired order
        """
        if len(elements) < 2:
            return

        # Extract just the elements
        element_tags = [el["element"] for el in elements]

        # Check if all elements are direct children of parent
        if not all(el.parent == parent for el in element_tags):
            logger.debug("Elements don't share same parent, skipping reorder")
            return

        # Get the position of the first element
        first_element = element_tags[0]
        insert_position = list(parent.children).index(first_element)

        # Remove all elements from their current positions
        for element in element_tags:
            element.extract()

        # Insert them back in the correct order
        for idx, element in enumerate(element_tags):
            parent.insert(insert_position + idx, element)

        self.changes.append(
            {
                "type": "dom_reordered",
                "parent": self._get_element_identifier(parent),
                "elements": [self._get_element_identifier(el) for el in element_tags],
                "count": len(element_tags),
                "reason": "Reordered to match visual reading order",
            }
        )

        logger.debug(f"Reordered {len(element_tags)} elements within {parent.name}")

    def _add_appropriate_negative_tabindex(self) -> None:
        """Add tabindex='-1' where appropriate (skip link targets, etc.)."""
        # Find skip link targets
        skip_links = self.soup.find_all("a", href=True)

        for link in skip_links:
            href = link.get("href", "")
            if href.startswith("#") and "skip" in link.get_text().lower():
                # Find the target
                target_id = href[1:]
                target = self.soup.find(id=target_id)

                if target and not target.has_attr("tabindex"):
                    target["tabindex"] = "-1"

                    self.changes.append(
                        {
                            "type": "tabindex_negative_added",
                            "element": self._get_element_identifier(target),
                            "element_type": target.name,
                            "old_value": None,
                            "new_value": "-1",
                            "reason": "Skip link target needs tabindex='-1'",
                        }
                    )

                    logger.debug(
                        f"Added tabindex='-1' to skip link target #{target_id}"
                    )

    def _is_positive_tabindex(self, element: Tag) -> bool:
        """Check if element has positive tabindex value."""
        try:
            tabindex = element.get("tabindex")
            if tabindex:
                return int(tabindex) > 0
        except (ValueError, TypeError):
            pass
        return False

    def _get_element_identifier(self, element: Tag) -> str:
        """Get a readable identifier for an element."""
        if element.has_attr("id"):
            return f"{element.name}#{element.get('id')}"
        elif element.has_attr("class"):
            classes = element.get("class", [])
            if classes:
                return f"{element.name}.{'.'.join(str(c) for c in classes[:2])}"
        return element.name

    def _find_element_from_issue(self, issue: Dict[str, Any]) -> Optional[Tag]:
        """Try to find an element based on issue information."""
        context = issue.get("context", {})
        element_name = context.get("element_name")

        if not element_name:
            return None

        # Try to find by class
        element_class = context.get("element_class")
        if element_class:
            elements = self.soup.find_all(element_name, class_=element_class)
            if elements:
                return elements[0]

        # Fallback: return first element of that type with tabindex="0"
        elements = self.soup.find_all(element_name, attrs={"tabindex": "0"})
        if elements:
            return elements[0]

        return None
