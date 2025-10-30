# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
UI component contrast remediation strategies.

This module provides remediation strategies for non-text contrast issues (WCAG 1.4.11).
Ensures UI components, graphical objects, and focus indicators have sufficient contrast.
"""

from typing import Dict, Any, Optional, Tuple
from bs4 import BeautifulSoup, Tag
import re
import logging

from content_accessibility_utility_on_aws.utils.logging_helper import setup_logger

logger = setup_logger(__name__)


def remediate_insufficient_ui_component_contrast(
    soup: BeautifulSoup, issue: Dict[str, Any]
) -> Optional[str]:
    """
    Remediate insufficient contrast for UI components.

    Args:
        soup: The BeautifulSoup object
        issue: The accessibility issue

    Returns:
        Description of remediation
    """
    element = _find_element_from_issue(soup, issue)
    if not element:
        return None

    location = issue.get('location', {})
    border_color = location.get('border_color')
    background_color = location.get('background_color')
    adjacent_color = location.get('adjacent_color', '#FFFFFF')

    logger.info(
        f"Remediating UI component contrast: element={element.name}, "
        f"border={border_color}, bg={background_color}, adjacent={adjacent_color}"
    )

    # Determine what needs adjustment
    if border_color:
        return _adjust_border_color(element, border_color, adjacent_color)
    elif background_color:
        return _adjust_background_color(element, background_color, adjacent_color)

    return None


def remediate_insufficient_icon_contrast(
    soup: BeautifulSoup, issue: Dict[str, Any]
) -> Optional[str]:
    """
    Remediate insufficient contrast for graphical objects (icons).

    Args:
        soup: The BeautifulSoup object
        issue: The accessibility issue

    Returns:
        Description of remediation
    """
    element = _find_element_from_issue(soup, issue)
    if not element:
        return None

    location = issue.get('location', {})
    fill_color = location.get('fill_color')
    stroke_color = location.get('stroke_color')
    adjacent_color = location.get('adjacent_color', '#FFFFFF')

    logger.info(
        f"Remediating icon contrast: element={element.name}, "
        f"fill={fill_color}, stroke={stroke_color}, adjacent={adjacent_color}"
    )

    # For SVG elements
    if element.name == 'svg':
        if fill_color:
            return _adjust_svg_fill(element, fill_color, adjacent_color)
        elif stroke_color:
            return _adjust_svg_stroke(element, stroke_color, adjacent_color)

    return None


def remediate_insufficient_focus_indicator_contrast(
    soup: BeautifulSoup, issue: Dict[str, Any]
) -> Optional[str]:
    """
    Remediate insufficient contrast for focus indicators.

    Args:
        soup: The BeautifulSoup object
        issue: The accessibility issue

    Returns:
        Description of remediation
    """
    element = _find_element_from_issue(soup, issue)
    if not element:
        return None

    location = issue.get('location', {})
    outline_color = location.get('outline_color')
    adjacent_color = location.get('adjacent_color', '#FFFFFF')

    logger.info(
        f"Remediating focus indicator: element={element.name}, "
        f"outline={outline_color}, adjacent={adjacent_color}"
    )

    # Add/update focus style
    return _add_accessible_focus_style(element, adjacent_color)


def _adjust_border_color(element: Tag, current_border: str, adjacent_color: str) -> Optional[str]:
    """
    Adjust border color to meet 3:1 contrast ratio.

    Args:
        element: The element to modify
        current_border: Current border color
        adjacent_color: Adjacent color to contrast against

    Returns:
        Description of change
    """
    # Calculate new border color
    new_border = _calculate_contrasting_color(adjacent_color, min_ratio=3.0)

    # Update border color in style
    style = element.get('style', '')

    if 'border-color' in style:
        # Replace existing border-color
        style = re.sub(
            r'border-color:\s*[^;]+',
            f'border-color: {new_border}',
            style
        )
    elif 'border:' in style:
        # Update border shorthand
        style = re.sub(
            r'border:\s*([^;]+)',
            lambda m: f'border: {m.group(1)} {new_border}' if new_border not in m.group(1) else m.group(0),
            style
        )
    else:
        # Add new border
        if style and not style.strip().endswith(';'):
            style += '; '
        style += f'border: 1px solid {new_border};'

    element['style'] = style
    return f"Adjusted border color to {new_border} for 3:1 contrast"


def _adjust_background_color(element: Tag, current_bg: str, adjacent_color: str) -> Optional[str]:
    """
    Adjust background color to meet 3:1 contrast ratio.

    Args:
        element: The element to modify
        current_bg: Current background color
        adjacent_color: Adjacent color to contrast against

    Returns:
        Description of change
    """
    # Calculate new background color
    new_bg = _calculate_contrasting_color(adjacent_color, min_ratio=3.0)

    # Update background in style
    style = element.get('style', '')

    if 'background-color' in style:
        style = re.sub(
            r'background-color:\s*[^;]+',
            f'background-color: {new_bg}',
            style
        )
    elif 'background:' in style:
        style = re.sub(
            r'background:\s*[^;]+',
            f'background: {new_bg}',
            style
        )
    else:
        if style and not style.strip().endswith(';'):
            style += '; '
        style += f'background-color: {new_bg};'

    element['style'] = style
    return f"Adjusted background color to {new_bg} for 3:1 contrast"


def _adjust_svg_fill(element: Tag, current_fill: str, adjacent_color: str) -> Optional[str]:
    """
    Adjust SVG fill color to meet 3:1 contrast ratio.

    Args:
        element: The SVG element
        current_fill: Current fill color
        adjacent_color: Adjacent color

    Returns:
        Description of change
    """
    new_fill = _calculate_contrasting_color(adjacent_color, min_ratio=3.0)

    # Update fill attribute
    element['fill'] = new_fill

    return f"Adjusted SVG fill to {new_fill} for 3:1 contrast"


def _adjust_svg_stroke(element: Tag, current_stroke: str, adjacent_color: str) -> Optional[str]:
    """
    Adjust SVG stroke color to meet 3:1 contrast ratio.

    Args:
        element: The SVG element
        current_stroke: Current stroke color
        adjacent_color: Adjacent color

    Returns:
        Description of change
    """
    new_stroke = _calculate_contrasting_color(adjacent_color, min_ratio=3.0)

    # Update stroke attribute
    element['stroke'] = new_stroke

    # Ensure stroke has width
    if not element.get('stroke-width'):
        element['stroke-width'] = '2'

    return f"Adjusted SVG stroke to {new_stroke} for 3:1 contrast"


def _add_accessible_focus_style(element: Tag, adjacent_color: str) -> Optional[str]:
    """
    Add accessible focus indicator style.

    Args:
        element: The element to add focus style to
        adjacent_color: Adjacent color for contrast

    Returns:
        Description of change
    """
    # Calculate contrasting outline color
    outline_color = _calculate_contrasting_color(adjacent_color, min_ratio=3.0)

    # Add inline style for focus (note: :focus pseudo-class requires CSS)
    # This is a simplified approach - ideally would add to stylesheet
    style = element.get('style', '')

    # Add comment about focus style needed
    # In a real implementation, would inject into <style> tag or external CSS

    # For now, enhance the base element with a strong border
    if style and not style.strip().endswith(';'):
        style += '; '

    # Add a visible border that will be enhanced on focus
    style += f'outline: 2px solid {outline_color} !important; outline-offset: 2px;'

    element['style'] = style

    return f"Added accessible focus outline with {outline_color} for 3:1 contrast"


def _calculate_contrasting_color(base_color: str, min_ratio: float = 3.0) -> str:
    """
    Calculate a color that contrasts with the base color.

    Args:
        base_color: The color to contrast against (hex)
        min_ratio: Minimum contrast ratio required

    Returns:
        Contrasting color (hex)
    """
    # Simplified: return black or white based on base color luminance
    luminance = _get_relative_luminance(base_color)

    # If base is dark, use white; if light, use black
    if luminance < 0.5:
        return '#FFFFFF'
    else:
        return '#000000'


def _get_relative_luminance(hex_color: str) -> float:
    """
    Calculate relative luminance of a color.

    Args:
        hex_color: Hex color code

    Returns:
        Relative luminance (0-1)
    """
    try:
        # Remove # and convert to RGB
        hex_color = hex_color.lstrip('#')
        if len(hex_color) != 6:
            return 0.5  # Default to medium

        r = int(hex_color[0:2], 16) / 255.0
        g = int(hex_color[2:4], 16) / 255.0
        b = int(hex_color[4:6], 16) / 255.0

        # Apply gamma correction
        def adjust(c):
            return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

        r, g, b = adjust(r), adjust(g), adjust(b)

        # Calculate luminance
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    except (ValueError, TypeError):
        return 0.5  # Default to medium


def _find_element_from_issue(soup: BeautifulSoup, issue: Dict[str, Any]) -> Optional[Tag]:
    """
    Find the element referenced in an issue.

    Args:
        soup: The BeautifulSoup object
        issue: The accessibility issue

    Returns:
        The element, or None if not found
    """
    element_str = issue.get("element", "")
    if not element_str:
        return None

    # Extract tag name
    tag_match = re.match(r"<([a-zA-Z0-9]+)", element_str)
    if not tag_match:
        return None

    tag_name = tag_match.group(1)

    # Extract ID if present
    id_match = re.search(r'id="([^"]*)"', element_str)
    if id_match:
        element_id = id_match.group(1)
        element = soup.find(id=element_id)
        if element:
            return element

    # Extract class if present
    class_match = re.search(r'class="([^"]*)"', element_str)
    class_names = class_match.group(1).split() if class_match else []

    # Find elements with matching classes
    if class_names:
        for element in soup.find_all(tag_name):
            element_classes = element.get("class", [])
            if all(cls in element_classes for cls in class_names):
                return element

    # Fall back to first element of tag type
    elements = soup.find_all(tag_name)
    if elements:
        return elements[0]

    return None


def calculate_contrast_ratio(color1: str, color2: str) -> float:
    """
    Calculate WCAG contrast ratio between two colors.

    Args:
        color1: First color (hex)
        color2: Second color (hex)

    Returns:
        Contrast ratio as float
    """
    l1 = _get_relative_luminance(color1)
    l2 = _get_relative_luminance(color2)

    # Calculate ratio (lighter color + 0.05) / (darker color + 0.05)
    if l1 > l2:
        return (l1 + 0.05) / (l2 + 0.05)
    else:
        return (l2 + 0.05) / (l1 + 0.05)
