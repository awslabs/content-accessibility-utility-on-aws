# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""Tab order accessibility checks.

This module provides checks for WCAG 2.4.3 Focus Order compliance.
"""

from typing import List, Dict, Any, Optional, Tuple
from bs4 import Tag
from content_accessibility_utility_on_aws.audit.base_check import AccessibilityCheck
from content_accessibility_utility_on_aws.utils.logging_helper import setup_logger

logger = setup_logger(__name__)


class TabOrderCheck(AccessibilityCheck):
    """Check for proper tab order (WCAG 2.4.3)."""

    # Interactive elements that should be in tab order
    INTERACTIVE_SELECTORS = [
        "a[href]",
        "button:not([disabled])",
        "input:not([disabled]):not([type='hidden'])",
        "select:not([disabled])",
        "textarea:not([disabled])",
        "area[href]",
        '[tabindex]:not([tabindex="-1"])',
    ]

    # Non-interactive elements that shouldn't have tabindex="0"
    NON_INTERACTIVE_ELEMENTS = ["div", "span", "p", "img", "section", "article"]

    def check(self) -> None:
        """
        Perform tab order checks on the document.

        Checks for:
        1. Positive tabindex values
        2. Unnecessary tabindex="0" on non-interactive elements
        3. Tab order vs visual order mismatches (if BDA data available)
        """
        logger.debug("Running tab order checks")

        # Check 1: Find elements with positive tabindex
        self._check_positive_tabindex()

        # Check 2: Find non-interactive elements with tabindex="0"
        self._check_unnecessary_tabindex_zero()

        # Check 3: Analyze tab order vs visual order
        self._check_tab_order_vs_visual_order()

        logger.debug(f"Tab order checks completed")

    def _check_positive_tabindex(self) -> None:
        """Check for elements with positive tabindex values."""
        elements_with_positive_tabindex = self.soup.find_all(
            lambda tag: tag.has_attr("tabindex") and self._is_positive_tabindex(tag)
        )

        for element in elements_with_positive_tabindex:
            tabindex_value = element.get("tabindex")

            self.add_issue(
                issue_type="positive-tabindex",
                wcag_criterion="2.4.3",
                severity="critical",
                element=element,
                description=f"Element has positive tabindex='{tabindex_value}' which disrupts natural tab order",
                context={
                    "element_name": element.name,
                    "tabindex": tabindex_value,
                    "element_id": element.get("id"),
                    "element_class": element.get("class"),
                    "recommendation": "Remove positive tabindex and restructure DOM order instead",
                },
            )

    def _check_unnecessary_tabindex_zero(self) -> None:
        """Check for non-interactive elements with tabindex='0'."""
        for element_type in self.NON_INTERACTIVE_ELEMENTS:
            elements = self.soup.find_all(element_type, attrs={"tabindex": "0"})

            for element in elements:
                # Skip if element has interactive role
                if self._has_interactive_role(element):
                    continue

                # Skip if element has onclick or other event handlers (might be interactive)
                if self._has_event_handlers(element):
                    continue

                self.add_issue(
                    issue_type="unnecessary-tabindex-zero",
                    wcag_criterion="2.4.3",
                    severity="minor",
                    element=element,
                    description=f"Non-interactive {element.name} element has tabindex='0'",
                    context={
                        "element_name": element.name,
                        "element_id": element.get("id"),
                        "element_class": element.get("class"),
                        "recommendation": "Remove tabindex='0' from non-interactive elements",
                    },
                )

    def _check_tab_order_vs_visual_order(self) -> None:
        """
        Check if tab order matches visual reading order.

        This uses BDA bounding box data if available to determine visual position.
        """
        # Find all interactive elements
        interactive_elements = self._get_interactive_elements()

        if len(interactive_elements) < 2:
            # Not enough elements to check order
            return

        # Get elements with position data
        elements_with_position = self._get_elements_with_position(interactive_elements)

        if len(elements_with_position) < 2:
            # No position data available
            logger.debug("No BDA position data available for tab order analysis")
            return

        # Sort by visual position (reading order)
        visual_order = self._sort_by_visual_position(elements_with_position)

        # Compare visual order with DOM order
        mismatches = self._find_order_mismatches(visual_order, elements_with_position)

        if mismatches:
            # Report tab order mismatch
            self.add_issue(
                issue_type="tab-order-mismatch",
                wcag_criterion="2.4.3",
                severity="major",
                element=None,
                description=f"Tab order does not match visual reading order ({len(mismatches)} mismatches found)",
                context={
                    "mismatches_count": len(mismatches),
                    "mismatches": mismatches[:5],  # First 5 mismatches
                    "total_interactive_elements": len(interactive_elements),
                    "recommendation": "Reorder elements in DOM to match visual reading order",
                },
            )

    def _get_interactive_elements(self) -> List[Tag]:
        """Get all interactive elements that should be in tab order."""
        interactive_elements = []

        for selector in self.INTERACTIVE_SELECTORS:
            elements = self.soup.select(selector)
            for element in elements:
                if element not in interactive_elements:
                    interactive_elements.append(element)

        return interactive_elements

    def _get_elements_with_position(self, elements: List[Tag]) -> List[Dict[str, Any]]:
        """
        Extract position data for elements from BDA attributes.

        Args:
            elements: List of elements to get position data for

        Returns:
            List of dicts with element and position data
        """
        elements_with_position = []

        for idx, element in enumerate(elements):
            # Look for BDA bounding box data in data attributes
            bbox_data = self._extract_bbox_data(element)

            if bbox_data:
                elements_with_position.append(
                    {
                        "element": element,
                        "dom_index": idx,
                        "bbox": bbox_data,
                        "element_id": element.get("id"),
                        "element_type": element.name,
                    }
                )

        return elements_with_position

    def _extract_bbox_data(self, element: Tag) -> Optional[Dict[str, float]]:
        """
        Extract bounding box data from element attributes.

        BDA may store this in data-bda-bbox or similar attributes.
        """
        # Check for common BDA data attributes
        if element.has_attr("data-bda-bbox"):
            try:
                # Parse bbox data (format: "x,y,width,height")
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

        # Check parent container for page-level position data
        page_container = element.find_parent(attrs={"data-page-bbox": True})
        if page_container:
            # Element is within a positioned page, but no specific bbox
            # We could estimate position, but for now return None
            pass

        return None

    def _sort_by_visual_position(
        self, elements_with_position: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Sort elements by visual reading order (top-to-bottom, left-to-right).

        Groups elements into rows based on Y-coordinate, then sorts by X within rows.
        """
        if not elements_with_position:
            return []

        # Group into rows (elements with similar Y coordinates)
        rows = self._group_into_rows(elements_with_position)

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
        """
        Group elements into rows based on Y-coordinate proximity.

        Args:
            elements_with_position: List of elements with position data
            threshold: Maximum Y-distance to consider elements in same row

        Returns:
            List of row dicts with elements and position info
        """
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

    def _find_order_mismatches(
        self, visual_order: List[Dict[str, Any]], dom_order: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Find elements whose visual order doesn't match DOM order.

        Args:
            visual_order: Elements sorted by visual position
            dom_order: Elements in original DOM order

        Returns:
            List of mismatches with details
        """
        mismatches = []

        # Create mapping of element to visual index
        visual_index_map = {
            id(el["element"]): idx for idx, el in enumerate(visual_order)
        }

        # Check for significant order inversions
        for i in range(len(dom_order) - 1):
            current_el = dom_order[i]
            next_el = dom_order[i + 1]

            current_visual_idx = visual_index_map.get(id(current_el["element"]))
            next_visual_idx = visual_index_map.get(id(next_el["element"]))

            # Skip if we don't have visual position for both
            if current_visual_idx is None or next_visual_idx is None:
                continue

            # Check if next element appears before current in visual order
            if next_visual_idx < current_visual_idx:
                mismatches.append(
                    {
                        "current_element": {
                            "type": current_el["element_type"],
                            "id": current_el["element_id"],
                            "dom_index": i,
                            "visual_index": current_visual_idx,
                        },
                        "next_element": {
                            "type": next_el["element_type"],
                            "id": next_el["element_id"],
                            "dom_index": i + 1,
                            "visual_index": next_visual_idx,
                        },
                        "description": f"Element at DOM position {i+1} appears before element at DOM position {i} visually",
                    }
                )

        return mismatches

    def _is_positive_tabindex(self, element: Tag) -> bool:
        """Check if element has positive tabindex value."""
        try:
            tabindex = element.get("tabindex")
            if tabindex:
                return int(tabindex) > 0
        except (ValueError, TypeError):
            pass
        return False

    def _has_interactive_role(self, element: Tag) -> bool:
        """Check if element has an interactive ARIA role."""
        role = element.get("role")
        interactive_roles = [
            "button",
            "link",
            "menuitem",
            "tab",
            "option",
            "checkbox",
            "radio",
            "textbox",
            "searchbox",
            "switch",
        ]
        return role in interactive_roles

    def _has_event_handlers(self, element: Tag) -> bool:
        """Check if element has event handler attributes."""
        event_attrs = [
            "onclick",
            "onkeydown",
            "onkeyup",
            "onkeypress",
            "onmousedown",
            "onmouseup",
            "onmouseover",
        ]
        return any(element.has_attr(attr) for attr in event_attrs)
