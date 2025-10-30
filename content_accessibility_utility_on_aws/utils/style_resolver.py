# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
CSS Style Resolution Utility.

This module provides functionality to parse CSS from various sources
(inline styles, style tags, external stylesheets) and resolve computed
styles for elements, with a focus on color properties for accessibility checks.
"""

import re
import logging
from typing import Dict, Optional, Tuple, List, Any
from bs4 import BeautifulSoup, Tag
from pathlib import Path

logger = logging.getLogger(__name__)


class StyleResolver:
    """
    Resolves computed styles for HTML elements by parsing CSS from multiple sources.

    This class handles:
    - Inline styles
    - <style> tags within HTML
    - External stylesheets (when provided)
    - CSS specificity and cascade resolution
    - Color property extraction
    """

    def __init__(self, soup: BeautifulSoup, stylesheet_paths: Optional[List[str]] = None):
        """
        Initialize the StyleResolver.

        Args:
            soup: BeautifulSoup object containing the HTML
            stylesheet_paths: Optional list of paths to external CSS files
        """
        self.soup = soup
        self.stylesheet_paths = stylesheet_paths or []
        self.parsed_rules: List[Dict[str, Any]] = []
        self._parse_all_styles()

    def _parse_all_styles(self) -> None:
        """Parse all CSS from style tags and external stylesheets."""
        # Parse style tags
        style_tags = self.soup.find_all("style")
        for style_tag in style_tags:
            if style_tag.string:
                self._parse_css_text(style_tag.string)

        # Parse external stylesheets
        for stylesheet_path in self.stylesheet_paths:
            try:
                with open(stylesheet_path, "r", encoding="utf-8") as f:
                    css_text = f.read()
                    self._parse_css_text(css_text)
            except Exception as e:
                logger.warning(f"Failed to parse stylesheet {stylesheet_path}: {e}")

    def _parse_css_text(self, css_text: str) -> None:
        """
        Parse CSS text and extract rules.

        Args:
            css_text: The CSS text to parse
        """
        # Remove comments
        css_text = re.sub(r'/\*.*?\*/', '', css_text, flags=re.DOTALL)

        # Simple CSS parser - matches selector { property: value; }
        # This handles basic CSS without complex selectors
        rule_pattern = r'([^{]+)\{([^}]+)\}'
        matches = re.finditer(rule_pattern, css_text)

        for match in matches:
            selector = match.group(1).strip()
            properties_text = match.group(2).strip()

            # Parse properties
            properties = self._parse_properties(properties_text)

            if properties:
                self.parsed_rules.append({
                    'selector': selector,
                    'properties': properties,
                    'specificity': self._calculate_specificity(selector)
                })

    def _parse_properties(self, properties_text: str) -> Dict[str, str]:
        """
        Parse CSS properties from a declaration block.

        Args:
            properties_text: The CSS properties text

        Returns:
            Dictionary of property names to values
        """
        properties = {}
        # Split by semicolons
        declarations = properties_text.split(';')

        for declaration in declarations:
            declaration = declaration.strip()
            if ':' in declaration:
                prop, value = declaration.split(':', 1)
                prop = prop.strip().lower()
                value = value.strip()
                properties[prop] = value

        return properties

    def _calculate_specificity(self, selector: str) -> Tuple[int, int, int]:
        """
        Calculate CSS specificity for a selector.

        Returns tuple of (id_count, class_count, element_count)
        Higher values = higher specificity

        Args:
            selector: The CSS selector

        Returns:
            Tuple of (id_count, class_count, element_count)
        """
        # Simple specificity calculation
        # Count IDs
        id_count = len(re.findall(r'#[\w-]+', selector))

        # Count classes, attributes, and pseudo-classes
        class_count = len(re.findall(r'\.[\w-]+', selector))
        class_count += len(re.findall(r'\[[\w-]+', selector))
        class_count += len(re.findall(r':[\w-]+(?!\()', selector))

        # Count elements and pseudo-elements
        # Remove classes and IDs first to avoid double counting
        temp_selector = re.sub(r'[.#][\w-]+', '', selector)
        element_count = len(re.findall(r'\b[a-z][\w-]*', temp_selector, re.IGNORECASE))
        element_count += len(re.findall(r'::[\w-]+', selector))

        return (id_count, class_count, element_count)

    def _element_matches_selector(self, element: Tag, selector: str) -> bool:
        """
        Check if an element matches a CSS selector.

        Args:
            element: The BeautifulSoup element
            selector: The CSS selector

        Returns:
            True if the element matches the selector
        """
        # Handle basic selectors
        selector = selector.strip()

        # Element selector (e.g., "p", "div")
        if re.match(r'^[a-z][\w-]*$', selector, re.IGNORECASE):
            return element.name == selector

        # ID selector (e.g., "#myid")
        if selector.startswith('#'):
            element_id = element.get('id', '')
            return element_id == selector[1:]

        # Class selector (e.g., ".myclass")
        if selector.startswith('.'):
            element_classes = element.get('class', [])
            return selector[1:] in element_classes

        # Element with class (e.g., "p.myclass")
        class_match = re.match(r'^([a-z][\w-]*)\.([a-z][\w-]*)$', selector, re.IGNORECASE)
        if class_match:
            elem_name, class_name = class_match.groups()
            element_classes = element.get('class', [])
            return element.name == elem_name and class_name in element_classes

        # Complex selectors - use CSS select
        try:
            # This is a fallback for complex selectors
            matches = self.soup.select(selector)
            return element in matches
        except Exception:
            return False

    def get_computed_style(self, element: Tag, property_name: str) -> Optional[str]:
        """
        Get the computed value of a CSS property for an element.

        This resolves the final value considering:
        1. Inline styles (highest priority)
        2. CSS rules from style tags and external stylesheets
        3. Inheritance (for inherited properties)
        4. Default values

        Args:
            element: The BeautifulSoup element
            property_name: The CSS property name (e.g., 'color', 'background-color')

        Returns:
            The computed property value, or None if not found
        """
        property_name = property_name.lower()

        # 1. Check inline style first (highest priority)
        inline_value = self._get_inline_style_property(element, property_name)
        if inline_value:
            return inline_value

        # 2. Check matching CSS rules
        matching_rules = []
        for rule in self.parsed_rules:
            if self._element_matches_selector(element, rule['selector']):
                if property_name in rule['properties']:
                    matching_rules.append(rule)

        # Sort by specificity (highest first)
        matching_rules.sort(key=lambda r: r['specificity'], reverse=True)

        # Return the value from the highest specificity rule
        if matching_rules:
            return matching_rules[0]['properties'][property_name]

        # 3. Check for inheritance (for inherited properties like color)
        if property_name in ['color']:
            parent = element.parent
            if parent and parent.name != '[document]':
                return self.get_computed_style(parent, property_name)

        # 4. Return default value
        return self._get_default_value(property_name)

    def _get_inline_style_property(self, element: Tag, property_name: str) -> Optional[str]:
        """
        Extract a property value from an element's inline style attribute.

        Args:
            element: The BeautifulSoup element
            property_name: The CSS property name

        Returns:
            The property value, or None if not found
        """
        style_attr = element.get('style', '')
        if not style_attr:
            return None

        # Parse inline style
        properties = self._parse_properties(style_attr)
        return properties.get(property_name)

    def _get_default_value(self, property_name: str) -> Optional[str]:
        """
        Get the default value for a CSS property.

        Args:
            property_name: The CSS property name

        Returns:
            The default value
        """
        defaults = {
            'color': '#000000',  # Black
            'background-color': 'transparent',
            'font-size': '16px',
            'font-weight': 'normal'
        }
        return defaults.get(property_name)

    def get_text_color(self, element: Tag) -> str:
        """
        Get the computed text color for an element.

        Args:
            element: The BeautifulSoup element

        Returns:
            The text color as a hex string (e.g., '#000000')
        """
        color = self.get_computed_style(element, 'color')
        if color:
            return self._normalize_color(color)
        return '#000000'  # Default to black

    def get_background_color(self, element: Tag) -> str:
        """
        Get the computed background color for an element.

        This walks up the parent tree to find the first non-transparent background.

        Args:
            element: The BeautifulSoup element

        Returns:
            The background color as a hex string (e.g., '#FFFFFF')
        """
        current = element
        while current and current.name != '[document]':
            bg_color = self.get_computed_style(current, 'background-color')

            if bg_color and bg_color != 'transparent':
                return self._normalize_color(bg_color)

            current = current.parent

        return '#FFFFFF'  # Default to white

    def _normalize_color(self, color: str) -> str:
        """
        Normalize a color value to a hex string.

        Args:
            color: The color value (hex, rgb, rgba, or named)

        Returns:
            The normalized color as a 6-digit hex string (e.g., '#FF0000')
        """
        color = color.strip().lower()

        # Handle hex colors
        if color.startswith('#'):
            # Remove the #
            hex_color = color[1:]

            # Convert 3-digit hex to 6-digit
            if len(hex_color) == 3:
                r, g, b = hex_color[0], hex_color[1], hex_color[2]
                return f'#{r}{r}{g}{g}{b}{b}'.upper()

            # 6-digit hex
            if len(hex_color) == 6:
                return f'#{hex_color}'.upper()

        # Handle rgb() and rgba()
        rgb_match = re.match(r'rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)', color)
        if rgb_match:
            r, g, b = map(int, rgb_match.groups())
            return f'#{r:02X}{g:02X}{b:02X}'

        # Handle named colors
        named_colors = {
            'black': '#000000',
            'white': '#FFFFFF',
            'red': '#FF0000',
            'green': '#008000',
            'blue': '#0000FF',
            'yellow': '#FFFF00',
            'gray': '#808080',
            'grey': '#808080',
            'transparent': 'transparent'
        }
        if color in named_colors:
            return named_colors[color]

        # If we can't parse it, return black as fallback
        return '#000000'

    def get_font_size(self, element: Tag) -> Optional[str]:
        """
        Get the computed font size for an element.

        Args:
            element: The BeautifulSoup element

        Returns:
            The font size value (e.g., '16px', '1.2em')
        """
        return self.get_computed_style(element, 'font-size')

    def get_font_weight(self, element: Tag) -> Optional[str]:
        """
        Get the computed font weight for an element.

        Args:
            element: The BeautifulSoup element

        Returns:
            The font weight value (e.g., 'bold', '700')
        """
        # Check if element is bold/strong
        if element.name in ['b', 'strong']:
            return 'bold'

        return self.get_computed_style(element, 'font-weight')
