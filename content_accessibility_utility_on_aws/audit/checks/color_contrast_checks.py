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

# Named color mapping (CSS Level 1 + common colors)
NAMED_COLORS = {
    "black": "#000000",
    "white": "#FFFFFF",
    "red": "#FF0000",
    "green": "#008000",
    "blue": "#0000FF",
    "yellow": "#FFFF00",
    "orange": "#FFA500",
    "purple": "#800080",
    "gray": "#808080",
    "grey": "#808080",
    "silver": "#C0C0C0",
    "navy": "#000080",
    "teal": "#008080",
    "maroon": "#800000",
    "aqua": "#00FFFF",
    "lime": "#00FF00",
    "fuchsia": "#FF00FF",
    "olive": "#808000",
    "transparent": None,
    "inherit": None,
    "initial": None,
    "currentcolor": None,
}


class ColorContrastCheck(AccessibilityCheck):
    """Check for proper color contrast (WCAG 1.4.3, 1.4.11)."""

    def __init__(self, soup, add_issue):
        """Initialize the check with CSS style parsing."""
        super().__init__(soup, add_issue)
        # Parse CSS from <style> blocks
        self._style_map = self._parse_style_blocks()

    def _parse_style_blocks(self) -> Dict[str, Dict[str, str]]:
        """
        Parse CSS from <style> blocks in the document.

        Returns:
            Dictionary mapping selectors to their color properties.
        """
        style_map = {}

        for style_tag in self.soup.find_all("style"):
            css_text = style_tag.get_text() if style_tag.string is None else style_tag.string
            if not css_text:
                continue

            # Simple CSS parsing - extract selector { property: value } pairs
            # This handles basic cases like: .class { color: red; }
            rule_pattern = r"([^{]+)\{([^}]+)\}"
            for match in re.finditer(rule_pattern, css_text):
                selector = match.group(1).strip()
                properties = match.group(2)

                # Parse color and background-color properties
                colors = {}
                color_match = re.search(
                    r"(?:^|;)\s*color\s*:\s*([^;]+)",
                    properties,
                    re.IGNORECASE
                )
                if color_match:
                    colors["color"] = color_match.group(1).strip()

                bg_match = re.search(
                    r"background(?:-color)?\s*:\s*([^;]+)",
                    properties,
                    re.IGNORECASE
                )
                if bg_match:
                    colors["background-color"] = bg_match.group(1).strip()

                if colors:
                    style_map[selector] = colors

        return style_map

    def _get_color_from_class(self, element: Tag, property_name: str) -> Optional[str]:
        """
        Get a color property value from an element's CSS classes.

        Args:
            element: The element to check
            property_name: 'color' or 'background-color'

        Returns:
            The color value or None
        """
        classes = element.get("class", [])
        if isinstance(classes, str):
            classes = classes.split()

        for class_name in classes:
            # Check for class selector
            selector = f".{class_name}"
            if selector in self._style_map:
                if property_name in self._style_map[selector]:
                    return self._style_map[selector][property_name]

        # Also check element type selectors
        if element.name in self._style_map:
            if property_name in self._style_map[element.name]:
                return self._style_map[element.name][property_name]

        return None

    def check(self) -> None:
        """
        Check if text elements have sufficient color contrast with their background.

        Issues:
            - insufficient-color-contrast: When text color doesn't have
                enough contrast with background
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

            # Get text and background colors
            text_color = self._get_text_color(element)
            bg_color = self._get_background_color(element)

            # If we couldn't determine colors, flag as potential issue
            if not text_color or not bg_color:
                # Only report if the element has inline style or class
                if element.get("style") or element.get("class"):
                    self.add_issue(
                        "potential-color-contrast-issue",
                        "1.4.3",
                        "minor",
                        element=element,
                        description="Potential color contrast issue - colors"
                        + "could not be determined automatically",
                    )
                continue

            # Calculate contrast ratio
            contrast_ratio = self._calculate_contrast_ratio(text_color, bg_color)

            # Determine minimum required contrast based on text size
            is_large_text = self._is_large_text(element)
            min_contrast = 3.0 if is_large_text else 4.5

            # Check if contrast is sufficient
            if contrast_ratio < min_contrast:
                self.add_issue(
                    "insufficient-color-contrast",
                    "1.4.3",
                    "major",
                    element=element,
                    description=f"Insufficient color contrast: {contrast_ratio:.2f}:1 "
                    + "(minimum required: {min_contrast}:1)",
                    location={
                        "text_color": text_color,
                        "background_color": bg_color,
                        "contrast_ratio": f"{contrast_ratio:.2f}:1",
                        "required_ratio": f"{min_contrast}:1",
                        "is_large_text": is_large_text,
                    },
                )

    def _get_text_color(self, element: Tag) -> Optional[str]:
        """
        Get the text color of an element.

        Checks in order of CSS specificity:
        1. Inline style
        2. Class-based styles from <style> blocks
        3. Element type styles from <style> blocks
        4. Inherited from parent
        5. Default (black)

        Args:
            element: The element to check

        Returns:
            The text color as a hex string, or None if it couldn't be determined
        """
        # 1. Check for inline color style (highest specificity)
        if element.get("style"):
            color_match = re.search(
                r"(?:^|;)\s*color\s*:\s*([^;]+)",
                element["style"],
                re.IGNORECASE
            )
            if color_match:
                color_val = color_match.group(1).strip()
                normalized = self._normalize_color(color_val)
                if normalized:
                    return normalized

        # 2. Check for class-based styles from <style> blocks
        class_color = self._get_color_from_class(element, "color")
        if class_color:
            normalized = self._normalize_color(class_color)
            if normalized:
                return normalized

        # 3. Check parent elements for inherited color
        parent = element.parent
        while parent and parent.name not in ["html", "[document]"]:
            # Check inline style
            if parent.get("style"):
                color_match = re.search(
                    r"(?:^|;)\s*color\s*:\s*([^;]+)",
                    parent["style"],
                    re.IGNORECASE
                )
                if color_match:
                    color_val = color_match.group(1).strip()
                    normalized = self._normalize_color(color_val)
                    if normalized:
                        return normalized

            # Check class-based styles
            class_color = self._get_color_from_class(parent, "color")
            if class_color:
                normalized = self._normalize_color(class_color)
                if normalized:
                    return normalized

            parent = parent.parent

        # Default to black if no color is specified
        return "#000000"

    def _get_background_color(self, element: Tag) -> Optional[str]:
        """
        Get the background color of an element.

        Checks the element and its ancestors for background color,
        considering inline styles, class-based styles, and inheritance.

        Args:
            element: The element to check

        Returns:
            The background color as a hex string, or None if it couldn't be determined
        """
        # Start with the element itself and walk up the DOM tree
        current = element
        while current and current.name not in ["html", "[document]"]:
            # 1. Check for inline background-color style
            if current.get("style"):
                bg_match = re.search(
                    r"background(?:-color)?\s*:\s*([^;]+)",
                    current["style"],
                    re.IGNORECASE
                )
                if bg_match:
                    bg_val = bg_match.group(1).strip()
                    # Handle 'background' shorthand - extract color if present
                    if not bg_val.startswith(('#', 'rgb', 'hsl')):
                        # Check if there's a color in the shorthand
                        color_in_bg = re.search(
                            r"(#[0-9a-fA-F]{3,6}|rgb[a]?\([^)]+\)|hsl[a]?\([^)]+\)|\b\w+\b)",
                            bg_val
                        )
                        if color_in_bg:
                            bg_val = color_in_bg.group(1)
                    normalized = self._normalize_color(bg_val)
                    if normalized:
                        return normalized

            # 2. Check for class-based background styles
            class_bg = self._get_color_from_class(current, "background-color")
            if class_bg:
                normalized = self._normalize_color(class_bg)
                if normalized:
                    return normalized

            current = current.parent

        # Default to white if no background color is specified
        return "#FFFFFF"

    def _normalize_color(self, color: str) -> Optional[str]:
        """
        Normalize a color value to a hex string.

        Handles multiple color formats:
        - Hex (#RGB, #RRGGBB)
        - RGB (rgb(r, g, b))
        - RGBA (rgba(r, g, b, a))
        - HSL (hsl(h, s%, l%))
        - Named colors (red, blue, etc.)

        Args:
            color: The color value to normalize

        Returns:
            The normalized color as a hex string, or None if invalid/transparent
        """
        if not color:
            return None

        color = color.strip().lower()

        # Check for named colors
        if color in NAMED_COLORS:
            return NAMED_COLORS[color]

        # Handle hex colors
        if color.startswith("#"):
            hex_part = color[1:]
            # Convert 3-digit hex to 6-digit
            if len(hex_part) == 3:
                r, g, b = hex_part[0], hex_part[1], hex_part[2]
                return f"#{r}{r}{g}{g}{b}{b}".upper()
            elif len(hex_part) == 6:
                return f"#{hex_part}".upper()
            elif len(hex_part) == 8:
                # Handle 8-digit hex (RRGGBBAA) - ignore alpha
                return f"#{hex_part[:6]}".upper()
            return None

        # Handle rgb() colors
        rgb_match = re.match(
            r"rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)",
            color
        )
        if rgb_match:
            r, g, b = map(int, rgb_match.groups())
            return f"#{r:02X}{g:02X}{b:02X}"

        # Handle rgba() colors (ignore alpha channel)
        rgba_match = re.match(
            r"rgba\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*[\d.]+\s*\)",
            color
        )
        if rgba_match:
            r, g, b = map(int, rgba_match.groups())
            return f"#{r:02X}{g:02X}{b:02X}"

        # Handle hsl() colors (supports decimal values for h, s, l)
        hsl_match = re.match(
            r"hsl\(\s*([\d.]+)\s*,\s*([\d.]+)%?\s*,\s*([\d.]+)%?\s*\)",
            color
        )
        if hsl_match:
            h, s, l = map(float, hsl_match.groups())
            rgb = self._hsl_to_rgb(h, s / 100, l / 100)
            return f"#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"

        # Handle hsla() colors (ignore alpha, supports decimal values)
        hsla_match = re.match(
            r"hsla\(\s*([\d.]+)\s*,\s*([\d.]+)%?\s*,\s*([\d.]+)%?\s*,\s*[\d.]+\s*\)",
            color
        )
        if hsla_match:
            h, s, l = map(float, hsla_match.groups())
            rgb = self._hsl_to_rgb(h, s / 100, l / 100)
            return f"#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"

        # If we can't parse the color, return None
        return None

    def _hsl_to_rgb(self, h: float, s: float, l: float) -> Tuple[int, int, int]:
        """
        Convert HSL color values to RGB.

        Args:
            h: Hue (0-360, can be decimal)
            s: Saturation (0-1)
            l: Lightness (0-1)

        Returns:
            Tuple of (r, g, b) values (0-255)
        """
        h = h / 360.0

        if s == 0:
            # Achromatic (gray)
            r = g = b = int(l * 255)
            return (r, g, b)

        def hue_to_rgb(p, q, t):
            if t < 0:
                t += 1
            if t > 1:
                t -= 1
            if t < 1/6:
                return p + (q - p) * 6 * t
            if t < 1/2:
                return q
            if t < 2/3:
                return p + (q - p) * (2/3 - t) * 6
            return p

        q = l * (1 + s) if l < 0.5 else l + s - l * s
        p = 2 * l - q

        r = int(hue_to_rgb(p, q, h + 1/3) * 255)
        g = int(hue_to_rgb(p, q, h) * 255)
        b = int(hue_to_rgb(p, q, h - 1/3) * 255)

        return (r, g, b)

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

        Args:
            element: The element to check

        Returns:
            True if the element contains large text, False otherwise
        """
        # Check for heading elements (h1, h2, h3)
        if element.name in ["h1", "h2", "h3"]:
            return True

        # Check for font-size style
        if element.get("style"):
            size_match = re.search(
                r"font-size:\s*(\d+)(px|pt|em|rem)", element["style"]
            )
            if size_match:
                size = float(size_match.group(1))
                unit = size_match.group(2)

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
            True if the element has bold text, False otherwise
        """
        # Check for bold element
        if element.name in ["b", "strong"]:
            return True

        # Check for font-weight style
        if element.get("style"):
            weight_match = re.search(
                r"font-weight:\s*(bold|700|800|900)", element["style"]
            )
            if weight_match:
                return True

        return False
