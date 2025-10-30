# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Color usage accessibility checks.

This module provides checks for proper use of color (WCAG 1.4.1).
Ensures that color is not the only visual means of conveying information.
"""

import re
from typing import Set, List
from bs4 import Tag

from content_accessibility_utility_on_aws.audit.base_check import AccessibilityCheck
from content_accessibility_utility_on_aws.utils.style_resolver import StyleResolver


class ColorUsageCheck(AccessibilityCheck):
    """Check that color is not the only means of conveying information (WCAG 1.4.1)."""

    def __init__(self, soup, add_issue_callback, stylesheet_paths=None):
        """
        Initialize the ColorUsageCheck.

        Args:
            soup: BeautifulSoup object
            add_issue_callback: Callback to report issues
            stylesheet_paths: Optional list of paths to external CSS files
        """
        super().__init__(soup, add_issue_callback)
        self.style_resolver = StyleResolver(soup, stylesheet_paths)

        # Common color-related keywords
        self.color_only_indicators = [
            'red', 'green', 'blue', 'yellow', 'orange', 'purple',
            'colored', 'color', 'colour'
        ]

    def check(self) -> None:
        """
        Check for instances where color is the only indicator of information.

        Common issues:
        - Form validation errors shown only in red
        - Required fields indicated only by red asterisks/color
        - Links distinguished from text only by color
        - Status indicators (success/error) shown only by color

        Issues:
            - color-only-indication: When color is the sole means of conveying information
        """
        # Check for required field indicators (red asterisks without labels)
        self._check_required_field_indicators()

        # Check for links without distinguishing features besides color
        self._check_link_indicators()

        # Check for form validation patterns
        self._check_form_validation_patterns()

        # Check for color-coded status messages
        self._check_status_messages()

    def _check_required_field_indicators(self) -> None:
        """
        Check for required field indicators that rely solely on color.

        Common pattern: Red asterisks (*) without aria-required or text labels.
        """
        # Find all form inputs
        inputs = self.soup.find_all(['input', 'select', 'textarea'])

        for input_elem in inputs:
            # Check if input has required attribute or aria-required
            has_required_attr = input_elem.get('required') is not None
            has_aria_required = input_elem.get('aria-required') == 'true'

            if has_required_attr or has_aria_required:
                continue  # Properly marked

            # Look for asterisks or "required" indicators near the input
            # Check label, parent, or previous siblings
            nearby_text = self._get_nearby_text(input_elem)

            if '*' in nearby_text or 'required' in nearby_text.lower():
                # Check if the asterisk/required indicator has only color styling
                asterisk_elem = self._find_asterisk_element(input_elem)

                if asterisk_elem:
                    # Check if it relies on color only
                    if self._relies_on_color_only(asterisk_elem):
                        self.add_issue(
                            "color-only-indication",
                            "1.4.1",
                            "major",
                            element=input_elem,
                            description="Required field indicator relies on color alone. "
                            + "Add 'required' attribute or visible text label.",
                            location={
                                "pattern": "required_field_indicator",
                                "indicator": "asterisk_or_color"
                            },
                        )

    def _check_link_indicators(self) -> None:
        """
        Check for links that are distinguished from text only by color.

        Links should have additional visual indicators like underlines or icons.
        """
        links = self.soup.find_all('a', href=True)

        for link in links:
            # Skip links with images
            if link.find('img'):
                continue

            # Get link text
            link_text = self.get_element_text(link).strip()
            if not link_text:
                continue  # Empty link, handled by other checks

            # Check if link has text-decoration
            text_decoration = self.style_resolver.get_computed_style(link, 'text-decoration')

            # Check if link has distinguishing features besides color
            has_underline = text_decoration and 'underline' in text_decoration
            has_icon = link.find(['i', 'svg', 'img']) is not None
            has_different_font = self._has_different_font_weight(link)

            # Check if link color differs from surrounding text
            link_color = self.style_resolver.get_text_color(link)
            parent = link.parent

            if parent and parent.name not in ['a', '[document]']:
                parent_color = self.style_resolver.get_text_color(parent)

                # If link color differs but no other indicators exist
                if link_color != parent_color and not (has_underline or has_icon or has_different_font):
                    self.add_issue(
                        "color-only-indication",
                        "1.4.1",
                        "major",
                        element=link,
                        description="Link is distinguished from text only by color. "
                        + "Add underline or other non-color indicator.",
                        location={
                            "pattern": "link_without_underline",
                            "link_color": link_color,
                            "parent_color": parent_color
                        },
                    )

    def _check_form_validation_patterns(self) -> None:
        """
        Check for form validation messages that rely solely on color.

        Common pattern: Error messages in red without icons or explicit labels.
        """
        # Look for common error message patterns
        error_patterns = [
            ('class', ['error', 'invalid', 'danger', 'alert-error', 'is-invalid']),
            ('role', ['alert']),
        ]

        potential_errors: Set[Tag] = set()

        for attr, values in error_patterns:
            for value in values:
                if attr == 'class':
                    elements = self.soup.find_all(class_=re.compile(value, re.I))
                else:
                    elements = self.soup.find_all(attrs={attr: value})
                potential_errors.update(elements)

        for error_elem in potential_errors:
            # Check if element has explicit error indicators besides color
            has_icon = error_elem.find(['i', 'svg']) is not None
            has_aria_label = error_elem.get('aria-label') or error_elem.get('aria-describedby')
            has_role_alert = error_elem.get('role') == 'alert'

            error_text = self.get_element_text(error_elem).lower()
            has_explicit_text = any(word in error_text for word in ['error', 'invalid', 'required', 'must'])

            # If element only has color styling
            if not (has_icon or has_aria_label or has_role_alert or has_explicit_text):
                # Check if it's styled with red/error colors
                text_color = self.style_resolver.get_text_color(error_elem)
                border_color = self.style_resolver.get_computed_style(error_elem, 'border-color')

                if self._is_error_color(text_color) or (border_color and self._is_error_color(border_color)):
                    self.add_issue(
                        "color-only-indication",
                        "1.4.1",
                        "major",
                        element=error_elem,
                        description="Form validation error indicated by color alone. "
                        + "Add icon, text label, or ARIA attributes.",
                        location={
                            "pattern": "form_validation_error",
                            "error_color": text_color or border_color
                        },
                    )

    def _check_status_messages(self) -> None:
        """
        Check for status messages that rely solely on color.

        Common patterns: Success (green), Warning (yellow), Error (red) badges.
        """
        # Look for status/badge elements
        status_selectors = [
            ('class', ['badge', 'status', 'label', 'tag', 'chip', 'pill']),
        ]

        potential_status: Set[Tag] = set()

        for attr, values in status_selectors:
            for value in values:
                elements = self.soup.find_all(class_=re.compile(value, re.I))
                potential_status.update(elements)

        for status_elem in potential_status:
            # Check if element has explicit indicators besides color
            has_icon = status_elem.find(['i', 'svg']) is not None
            status_text = self.get_element_text(status_elem).strip()

            # Check if text explicitly conveys meaning
            has_meaningful_text = len(status_text) > 2 and any(
                word in status_text.lower()
                for word in ['success', 'error', 'warning', 'info', 'complete', 'pending', 'failed', 'active', 'inactive']
            )

            if not (has_icon or has_meaningful_text):
                # Check if it uses status colors
                bg_color = self.style_resolver.get_background_color(status_elem)

                if self._is_status_color(bg_color):
                    self.add_issue(
                        "color-only-indication",
                        "1.4.1",
                        "major",
                        element=status_elem,
                        description="Status indicator relies on color alone. "
                        + "Add icon or explicit text label.",
                        location={
                            "pattern": "status_badge",
                            "background_color": bg_color
                        },
                    )

    def _get_nearby_text(self, element: Tag, max_distance: int = 3) -> str:
        """
        Get text from nearby elements (labels, siblings, parents).

        Args:
            element: The element to check around
            max_distance: Maximum distance to search

        Returns:
            Combined nearby text
        """
        nearby_text = []

        # Check label
        element_id = element.get('id')
        if element_id:
            label = self.soup.find('label', attrs={'for': element_id})
            if label:
                nearby_text.append(self.get_element_text(label))

        # Check parent label
        parent_label = element.find_parent('label')
        if parent_label:
            nearby_text.append(self.get_element_text(parent_label))

        # Check previous siblings
        prev_sibling = element.previous_sibling
        distance = 0
        while prev_sibling and distance < max_distance:
            if hasattr(prev_sibling, 'get_text'):
                nearby_text.append(prev_sibling.get_text())
            distance += 1
            prev_sibling = prev_sibling.previous_sibling

        return ' '.join(nearby_text)

    def _find_asterisk_element(self, input_elem: Tag) -> Tag:
        """
        Find the asterisk or required indicator element near an input.

        Args:
            input_elem: The input element

        Returns:
            The asterisk element if found
        """
        # Check label
        element_id = input_elem.get('id')
        if element_id:
            label = self.soup.find('label', attrs={'for': element_id})
            if label:
                # Look for span with asterisk
                asterisk = label.find('span', string=re.compile(r'\*'))
                if asterisk:
                    return asterisk

        # Check parent elements
        parent = input_elem.parent
        if parent:
            asterisk = parent.find('span', string=re.compile(r'\*'))
            if asterisk:
                return asterisk

        return None

    def _relies_on_color_only(self, element: Tag) -> bool:
        """
        Check if an element relies on color as the only indicator.

        Args:
            element: The element to check

        Returns:
            True if element relies only on color
        """
        # Check if element has color styling
        text_color = self.style_resolver.get_text_color(element)

        # Check if it's a distinctive color (red for required)
        if not self._is_error_color(text_color):
            return False

        # Check if there are other indicators
        # Check for bold, size, or other styling
        font_weight = self.style_resolver.get_font_weight(element)
        is_bold = font_weight and (font_weight == 'bold' or (font_weight.isdigit() and int(font_weight) >= 700))

        # Check for aria attributes
        has_aria = element.get('aria-label') or element.get('aria-describedby')

        # If only color is used (red text, no bold, no aria)
        return not (is_bold or has_aria)

    def _has_different_font_weight(self, element: Tag) -> bool:
        """
        Check if element has a different font weight from parent.

        Args:
            element: The element to check

        Returns:
            True if font weight differs significantly
        """
        element_weight = self.style_resolver.get_font_weight(element)
        parent = element.parent

        if parent and parent.name not in ['[document]', 'html', 'body']:
            parent_weight = self.style_resolver.get_font_weight(parent)

            # Compare weights
            if element_weight != parent_weight:
                return True

        return False

    def _is_error_color(self, color: str) -> bool:
        """
        Check if a color is typically used for errors (red-ish).

        Args:
            color: Hex color string

        Returns:
            True if color is error-like
        """
        if not color or color == 'transparent':
            return False

        # Convert hex to RGB
        try:
            hex_color = color.lstrip('#')
            if len(hex_color) != 6:
                return False

            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)

            # Red-ish if R > 150 and R > G and R > B
            return r > 150 and r > g and r > b
        except (ValueError, TypeError):
            return False

    def _is_status_color(self, color: str) -> bool:
        """
        Check if a color is typically used for status indicators.

        Args:
            color: Hex color string

        Returns:
            True if color is status-like (green, yellow, red, blue)
        """
        if not color or color == 'transparent':
            return False

        # Convert hex to RGB
        try:
            hex_color = color.lstrip('#')
            if len(hex_color) != 6:
                return False

            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)

            # Check for distinctive colors
            # Green: G > 150 and G > R and G > B
            is_green = g > 150 and g > r and g > b

            # Yellow: R > 150 and G > 150 and B < 100
            is_yellow = r > 150 and g > 150 and b < 100

            # Red: R > 150 and R > G and R > B
            is_red = r > 150 and r > g and r > b

            # Blue: B > 150 and B > R and B > G
            is_blue = b > 150 and b > r and b > g

            return is_green or is_yellow or is_red or is_blue
        except (ValueError, TypeError):
            return False
