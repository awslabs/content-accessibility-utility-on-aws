# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Color contrast accessibility checks.

This module provides checks for proper color contrast between text and background.
"""

import re
from typing import Tuple, Optional, Dict
from bs4 import Tag

from content_accessibility_utility_on_aws.audit.base_check import AccessibilityCheck
from content_accessibility_utility_on_aws.utils.style_resolver import StyleResolver


class ColorContrastCheck(AccessibilityCheck):
    """Check for proper color contrast (WCAG 1.4.3, 1.4.6)."""

    def __init__(self, soup, add_issue_callback, contrast_level: str = 'AA', stylesheet_paths: Optional[list] = None):
        """
        Initialize the ColorContrastCheck.

        Args:
            soup: BeautifulSoup object
            add_issue_callback: Callback to report issues
            contrast_level: WCAG conformance level ('AA' or 'AAA')
            stylesheet_paths: Optional list of paths to external CSS files
        """
        super().__init__(soup, add_issue_callback)
        self.contrast_level = contrast_level.upper()
        self.style_resolver = StyleResolver(soup, stylesheet_paths)

    def check(self) -> None:
        """
        Check if text elements have sufficient color contrast with their background.

        Supports both AA and AAA conformance levels:
        - AA: 4.5:1 for normal text, 3:1 for large text (WCAG 1.4.3)
        - AAA: 7:1 for normal text, 4.5:1 for large text (WCAG 1.4.6)

        Issues:
            - insufficient-color-contrast: When text color doesn't meet AA requirements
            - insufficient-color-contrast-aaa: When text color doesn't meet AAA requirements
            - potential-color-contrast-issue: When contrast can't be determined automatically
        """
        # Elements that typically contain text
        text_elements = self.soup.find_all(
            [
                "p",
                "h1",
                "h2",
                "h3",
                "h4",
                "h5",
                "h6",
                "a",
                "span",
                "div",
                "li",
                "td",
                "th",
            ]
        )

        for element in text_elements:
            # Skip empty elements
            if not self.get_element_text(element).strip():
                continue

            # Get text and background colors using StyleResolver
            text_color = self.style_resolver.get_text_color(element)
            bg_color = self.style_resolver.get_background_color(element)

            # If colors are transparent or couldn't be determined, try fallback
            if not text_color or text_color == 'transparent':
                text_color = self._get_text_color(element)
            if not bg_color or bg_color == 'transparent':
                bg_color = self._get_background_color(element)

            # If we still couldn't determine colors, flag as potential issue
            if not text_color or not bg_color or text_color == 'transparent' or bg_color == 'transparent':
                # Only report if the element has inline style or class
                if element.get("style") or element.get("class"):
                    self.add_issue(
                        "potential-color-contrast-issue",
                        "1.4.3",
                        "minor",
                        element=element,
                        description="Potential color contrast issue - colors "
                        + "could not be determined automatically",
                    )
                continue

            # Calculate contrast ratio
            contrast_ratio = self._calculate_contrast_ratio(text_color, bg_color)

            # Determine minimum required contrast based on text size and level
            is_large_text = self._is_large_text(element)

            # AA Level (WCAG 1.4.3)
            min_contrast_aa = 3.0 if is_large_text else 4.5

            # Check AA compliance
            if contrast_ratio < min_contrast_aa:
                self.add_issue(
                    "insufficient-color-contrast",
                    "1.4.3",
                    "major",
                    element=element,
                    description=f"Insufficient color contrast: {contrast_ratio:.2f}:1 "
                    + f"(minimum required for AA: {min_contrast_aa}:1)",
                    location={
                        "text_color": text_color,
                        "background_color": bg_color,
                        "contrast_ratio": f"{contrast_ratio:.2f}:1",
                        "required_ratio_aa": f"{min_contrast_aa}:1",
                        "is_large_text": is_large_text,
                    },
                )

            # AAA Level (WCAG 1.4.6) - if checking for AAA
            if self.contrast_level == 'AAA':
                min_contrast_aaa = 4.5 if is_large_text else 7.0

                if contrast_ratio < min_contrast_aaa:
                    self.add_issue(
                        "insufficient-color-contrast-aaa",
                        "1.4.6",
                        "minor",  # AAA is enhancement, so minor severity
                        element=element,
                        description=f"Insufficient color contrast for AAA: {contrast_ratio:.2f}:1 "
                        + f"(minimum required for AAA: {min_contrast_aaa}:1)",
                        location={
                            "text_color": text_color,
                            "background_color": bg_color,
                            "contrast_ratio": f"{contrast_ratio:.2f}:1",
                            "required_ratio_aaa": f"{min_contrast_aaa}:1",
                            "is_large_text": is_large_text,
                        },
                    )

    def _get_text_color(self, element: Tag) -> Optional[str]:
        """
        Get the text color of an element.

        Args:
            element: The element to check

        Returns:
            The text color as a hex string, or None if it couldn't be determined
        """
        # Check for inline color style
        if element.get("style"):
            color_match = re.search(
                r"color:\s*(#[0-9a-fA-F]{3,6}|rgb\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*\))",
                element["style"],
            )
            if color_match:
                return self._normalize_color(color_match.group(1))

        # Default to black if no color is specified
        return "#000000"

    def _get_background_color(self, element: Tag) -> Optional[str]:
        """
        Get the background color of an element.

        Args:
            element: The element to check

        Returns:
            The background color as a hex string, or None if it couldn't be determined
        """
        # Check for inline background-color style
        if element.get("style"):
            bg_match = re.search(
                r"background-color:\s*(#[0-9a-fA-F]{3,6}|rgb\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*\))",
                element["style"],
            )
            if bg_match:
                return self._normalize_color(bg_match.group(1))

        # Check parent elements for background color
        parent = element.parent
        while parent and parent.name != "html":
            if parent.get("style"):
                bg_match = re.search(
                    r"background-color:\s*(#[0-9a-fA-F]{3,6}|rgb\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*\))",
                    parent["style"],
                )
                if bg_match:
                    return self._normalize_color(bg_match.group(1))
            parent = parent.parent

        # Default to white if no background color is specified
        return "#FFFFFF"

    def _normalize_color(self, color: str) -> str:
        """
        Normalize a color value to a hex string.

        Args:
            color: The color value to normalize

        Returns:
            The normalized color as a hex string
        """
        # Handle hex colors
        if color.startswith("#"):
            # Convert 3-digit hex to 6-digit
            if len(color) == 4:
                r, g, b = color[1], color[2], color[3]
                return f"#{r}{r}{g}{g}{b}{b}".upper()
            return color.upper()

        # Handle rgb() colors
        rgb_match = re.match(r"rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)", color)
        if rgb_match:
            r, g, b = map(int, rgb_match.groups())
            return f"#{r:02X}{g:02X}{b:02X}"

        return color

    def _calculate_contrast_ratio(self, color1: str, color2: str) -> float:
        """
        Calculate the contrast ratio between two colors.

        Args:
            color1: The first color as a hex string
            color2: The second color as a hex string

        Returns:
            The contrast ratio as a float
        """
        # Convert hex to RGB
        rgb1 = self._hex_to_rgb(color1)
        rgb2 = self._hex_to_rgb(color2)

        # Calculate relative luminance
        l1 = self._relative_luminance(rgb1)
        l2 = self._relative_luminance(rgb2)

        # Calculate contrast ratio
        if l1 > l2:
            return (l1 + 0.05) / (l2 + 0.05)
        else:
            return (l2 + 0.05) / (l1 + 0.05)

    def _hex_to_rgb(self, hex_color: str) -> Tuple[int, int, int]:
        """
        Convert a hex color to RGB.

        Args:
            hex_color: The hex color string

        Returns:
            A tuple of (r, g, b) values
        """
        hex_color = hex_color.lstrip("#")
        return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))

    def _relative_luminance(self, rgb: Tuple[int, int, int]) -> float:
        """
        Calculate the relative luminance of an RGB color.

        Args:
            rgb: The RGB color as a tuple of (r, g, b) values

        Returns:
            The relative luminance as a float
        """
        r, g, b = rgb

        # Normalize RGB values
        r = r / 255
        g = g / 255
        b = b / 255

        # Apply gamma correction
        r = self._gamma_correct(r)
        g = self._gamma_correct(g)
        b = self._gamma_correct(b)

        # Calculate luminance
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    def _gamma_correct(self, value: float) -> float:
        """
        Apply gamma correction to a color channel value.

        Args:
            value: The color channel value (0-1)

        Returns:
            The gamma-corrected value
        """
        if value <= 0.03928:
            return value / 12.92
        else:
            return ((value + 0.055) / 1.055) ** 2.4

    def _is_large_text(self, element: Tag) -> bool:
        """
        Determine if an element contains large text.

        Large text is defined as:
        - 18pt (24px) or larger, or
        - 14pt (18.67px) or larger if bold (font-weight >= 700)

        Args:
            element: The element to check

        Returns:
            True if the element contains large text, False otherwise
        """
        # Check for heading elements (h1, h2, h3)
        if element.name in ["h1", "h2", "h3"]:
            return True

        # Get computed font size using StyleResolver
        font_size_str = self.style_resolver.get_font_size(element)
        if font_size_str:
            size_match = re.search(
                r"(\d+\.?\d*)(px|pt|em|rem)?", font_size_str
            )
            if size_match:
                size = float(size_match.group(1))
                unit = size_match.group(2) if size_match.group(2) else 'px'

                # Convert to pixels (approximate)
                if unit == "pt":
                    size = size * 1.333
                elif unit == "em" or unit == "rem":
                    size = size * 16

                # Large text is 18pt (24px) or 14pt (18.67px) bold
                if size >= 24:
                    return True
                if size >= 18.67 and self._is_bold(element):
                    return True

        return False

    def _is_bold(self, element: Tag) -> bool:
        """
        Determine if an element has bold text.

        Args:
            element: The element to check

        Returns:
            True if the element has bold text (font-weight >= 700), False otherwise
        """
        # Check for bold element
        if element.name in ["b", "strong"]:
            return True

        # Get computed font weight using StyleResolver
        font_weight = self.style_resolver.get_font_weight(element)
        if font_weight:
            # Check if it's bold
            if font_weight == 'bold' or font_weight == 'bolder':
                return True

            # Check numeric weight (700 or higher is bold)
            try:
                weight_num = int(font_weight)
                if weight_num >= 700:
                    return True
            except (ValueError, TypeError):
                pass

        return False


class NonTextContrastCheck(AccessibilityCheck):
    """Check for proper non-text contrast (WCAG 1.4.11)."""

    def __init__(self, soup, add_issue_callback, stylesheet_paths: Optional[list] = None):
        """
        Initialize the NonTextContrastCheck.

        Args:
            soup: BeautifulSoup object
            add_issue_callback: Callback to report issues
            stylesheet_paths: Optional list of paths to external CSS files
        """
        super().__init__(soup, add_issue_callback)
        self.style_resolver = StyleResolver(soup, stylesheet_paths)

    def check(self) -> None:
        """
        Check if UI components and graphical objects have sufficient contrast.

        WCAG 1.4.11 (Level AA) requires a contrast ratio of at least 3:1 for:
        - User interface components (visual information required to identify)
        - Graphical objects (parts required to understand content)
        - Focus indicators

        Issues:
            - insufficient-ui-component-contrast: UI component contrast < 3:1
            - insufficient-icon-contrast: Graphical object contrast < 3:1
            - insufficient-focus-indicator-contrast: Focus indicator contrast < 3:1
        """
        # Check interactive UI components
        self._check_ui_components()

        # Check SVG icons and graphical objects
        self._check_graphical_objects()

    def _check_ui_components(self) -> None:
        """Check contrast for interactive UI components."""
        # UI components to check
        ui_elements = self.soup.find_all(['button', 'input', 'select', 'textarea', 'a'])

        for element in ui_elements:
            # Skip if element is hidden or has no visual presence
            style_attr = element.get('style', '')
            if 'display:none' in style_attr or 'visibility:hidden' in style_attr:
                continue

            # Get border and background colors
            border_color = self._get_border_color(element)
            bg_color = self.style_resolver.get_background_color(element)

            # Get adjacent color (parent background or page background)
            adjacent_color = self._get_adjacent_color(element)

            # Check border contrast
            if border_color and border_color != 'transparent' and adjacent_color:
                contrast_ratio = self._calculate_contrast_ratio(border_color, adjacent_color)

                if contrast_ratio < 3.0:
                    self.add_issue(
                        "insufficient-ui-component-contrast",
                        "1.4.11",
                        "major",
                        element=element,
                        description=f"UI component border has insufficient contrast: {contrast_ratio:.2f}:1 "
                        + f"(minimum required: 3:1)",
                        location={
                            "border_color": border_color,
                            "adjacent_color": adjacent_color,
                            "contrast_ratio": f"{contrast_ratio:.2f}:1",
                            "required_ratio": "3:1",
                        },
                    )

            # Check background contrast for buttons and inputs
            if element.name in ['button', 'input', 'select', 'textarea']:
                if bg_color and bg_color != 'transparent' and adjacent_color:
                    contrast_ratio = self._calculate_contrast_ratio(bg_color, adjacent_color)

                    if contrast_ratio < 3.0:
                        self.add_issue(
                            "insufficient-ui-component-contrast",
                            "1.4.11",
                            "major",
                            element=element,
                            description=f"UI component background has insufficient contrast: {contrast_ratio:.2f}:1 "
                            + f"(minimum required: 3:1)",
                            location={
                                "background_color": bg_color,
                                "adjacent_color": adjacent_color,
                                "contrast_ratio": f"{contrast_ratio:.2f}:1",
                                "required_ratio": "3:1",
                            },
                        )

            # Check focus indicator (if :focus styles exist)
            self._check_focus_indicator(element)

    def _check_graphical_objects(self) -> None:
        """Check contrast for graphical objects like icons."""
        # Check SVG elements
        svg_elements = self.soup.find_all('svg')

        for svg in svg_elements:
            # Check if SVG is decorative (has aria-hidden or role="presentation")
            if svg.get('aria-hidden') == 'true' or svg.get('role') == 'presentation':
                continue

            # Get SVG fill and stroke colors
            fill_color = svg.get('fill')
            stroke_color = svg.get('stroke')

            # Get adjacent color
            adjacent_color = self._get_adjacent_color(svg)

            # Check fill contrast
            if fill_color and fill_color not in ['none', 'transparent'] and adjacent_color:
                normalized_fill = self.style_resolver._normalize_color(fill_color)
                if normalized_fill != 'transparent':
                    contrast_ratio = self._calculate_contrast_ratio(normalized_fill, adjacent_color)

                    if contrast_ratio < 3.0:
                        self.add_issue(
                            "insufficient-icon-contrast",
                            "1.4.11",
                            "major",
                            element=svg,
                            description=f"Graphical object has insufficient contrast: {contrast_ratio:.2f}:1 "
                            + f"(minimum required: 3:1)",
                            location={
                                "fill_color": normalized_fill,
                                "adjacent_color": adjacent_color,
                                "contrast_ratio": f"{contrast_ratio:.2f}:1",
                                "required_ratio": "3:1",
                            },
                        )

            # Check stroke contrast
            if stroke_color and stroke_color not in ['none', 'transparent'] and adjacent_color:
                normalized_stroke = self.style_resolver._normalize_color(stroke_color)
                if normalized_stroke != 'transparent':
                    contrast_ratio = self._calculate_contrast_ratio(normalized_stroke, adjacent_color)

                    if contrast_ratio < 3.0:
                        self.add_issue(
                            "insufficient-icon-contrast",
                            "1.4.11",
                            "major",
                            element=svg,
                            description=f"Graphical object stroke has insufficient contrast: {contrast_ratio:.2f}:1 "
                            + f"(minimum required: 3:1)",
                            location={
                                "stroke_color": normalized_stroke,
                                "adjacent_color": adjacent_color,
                                "contrast_ratio": f"{contrast_ratio:.2f}:1",
                                "required_ratio": "3:1",
                            },
                        )

    def _check_focus_indicator(self, element: Tag) -> None:
        """
        Check if element has a visible focus indicator with sufficient contrast.

        Args:
            element: The element to check
        """
        # Look for :focus styles in style tags
        # This is a simplified check - full implementation would need CSS parser
        # For now, we'll check if there's any outline or border style

        focus_styles = self._get_focus_styles(element)
        if not focus_styles:
            # If no explicit focus styles, browser default is used
            # We won't flag this as it's the browser's responsibility
            return

        # Check outline color contrast
        if 'outline-color' in focus_styles or 'outline' in focus_styles:
            outline_color = focus_styles.get('outline-color', focus_styles.get('outline', ''))
            if outline_color:
                # Parse color from outline shorthand if needed
                color_match = re.search(r'#[0-9a-fA-F]{3,6}|rgb\([^)]+\)', outline_color)
                if color_match:
                    outline_color = color_match.group(0)
                    normalized_outline = self.style_resolver._normalize_color(outline_color)
                    adjacent_color = self._get_adjacent_color(element)

                    if adjacent_color:
                        contrast_ratio = self._calculate_contrast_ratio(normalized_outline, adjacent_color)

                        if contrast_ratio < 3.0:
                            self.add_issue(
                                "insufficient-focus-indicator-contrast",
                                "1.4.11",
                                "major",
                                element=element,
                                description=f"Focus indicator has insufficient contrast: {contrast_ratio:.2f}:1 "
                                + f"(minimum required: 3:1)",
                                location={
                                    "outline_color": normalized_outline,
                                    "adjacent_color": adjacent_color,
                                    "contrast_ratio": f"{contrast_ratio:.2f}:1",
                                    "required_ratio": "3:1",
                                },
                            )

    def _get_border_color(self, element: Tag) -> Optional[str]:
        """
        Get the border color of an element.

        Args:
            element: The element to check

        Returns:
            The border color as a hex string, or None
        """
        border_color = self.style_resolver.get_computed_style(element, 'border-color')
        if border_color:
            return self.style_resolver._normalize_color(border_color)

        # Check for border shorthand
        border = self.style_resolver.get_computed_style(element, 'border')
        if border:
            # Try to extract color from border shorthand
            color_match = re.search(r'#[0-9a-fA-F]{3,6}|rgb\([^)]+\)', border)
            if color_match:
                return self.style_resolver._normalize_color(color_match.group(0))

        return None

    def _get_adjacent_color(self, element: Tag) -> str:
        """
        Get the adjacent color (parent background) for an element.

        Args:
            element: The element to check

        Returns:
            The adjacent color as a hex string
        """
        parent = element.parent
        if parent and parent.name != '[document]':
            return self.style_resolver.get_background_color(parent)
        return '#FFFFFF'  # Default to white

    def _get_focus_styles(self, element: Tag) -> Dict[str, str]:
        """
        Get focus styles for an element.

        This is a simplified implementation that checks for inline focus styles.
        A full implementation would parse CSS :focus selectors.

        Args:
            element: The element to check

        Returns:
            Dictionary of focus style properties
        """
        # For now, return empty dict as we'd need more sophisticated CSS parsing
        # This is a placeholder for future enhancement
        return {}

    def _calculate_contrast_ratio(self, color1: str, color2: str) -> float:
        """
        Calculate the contrast ratio between two colors.

        Args:
            color1: The first color as a hex string
            color2: The second color as a hex string

        Returns:
            The contrast ratio as a float
        """
        # Convert hex to RGB
        rgb1 = self._hex_to_rgb(color1)
        rgb2 = self._hex_to_rgb(color2)

        # Calculate relative luminance
        l1 = self._relative_luminance(rgb1)
        l2 = self._relative_luminance(rgb2)

        # Calculate contrast ratio
        if l1 > l2:
            return (l1 + 0.05) / (l2 + 0.05)
        else:
            return (l2 + 0.05) / (l1 + 0.05)

    def _hex_to_rgb(self, hex_color: str) -> Tuple[int, int, int]:
        """
        Convert a hex color to RGB.

        Args:
            hex_color: The hex color string

        Returns:
            A tuple of (r, g, b) values
        """
        hex_color = hex_color.lstrip("#")
        return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))

    def _relative_luminance(self, rgb: Tuple[int, int, int]) -> float:
        """
        Calculate the relative luminance of an RGB color.

        Args:
            rgb: The RGB color as a tuple of (r, g, b) values

        Returns:
            The relative luminance as a float
        """
        r, g, b = rgb

        # Normalize RGB values
        r = r / 255
        g = g / 255
        b = b / 255

        # Apply gamma correction
        r = self._gamma_correct(r)
        g = self._gamma_correct(g)
        b = self._gamma_correct(b)

        # Calculate luminance
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    def _gamma_correct(self, value: float) -> float:
        """
        Apply gamma correction to a color channel value.

        Args:
            value: The color channel value (0-1)

        Returns:
            The gamma-corrected value
        """
        if value <= 0.03928:
            return value / 12.92
        else:
            return ((value + 0.055) / 1.055) ** 2.4
