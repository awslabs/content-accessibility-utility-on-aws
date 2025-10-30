# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Color contrast accessibility remediation strategies.

This module provides remediation strategies for color contrast-related accessibility issues.
Includes both simple programmatic fixes and AI-powered color suggestions.
"""

from typing import Dict, Any, Optional, Tuple
from bs4 import BeautifulSoup
import re
import logging

from content_accessibility_utility_on_aws.utils.logging_helper import setup_logger

logger = setup_logger(__name__)


def remediate_insufficient_color_contrast(
    soup: BeautifulSoup, issue: Dict[str, Any]
) -> Optional[str]:
    """
    Remediate insufficient color contrast by adjusting text or background color.

    Args:
        soup: The BeautifulSoup object representing the HTML document
        issue: The accessibility issue to remediate

    Returns:
        A message describing the remediation, or None if no remediation was performed
    """
    # Find the element from the issue
    element_str = issue.get("element", "")
    if not element_str:
        return None

    # Extract element tag name
    tag_match = re.match(r"<([a-zA-Z0-9]+)", element_str)
    if not tag_match:
        return None

    tag_name = tag_match.group(1)

    # Try to find the element in the document
    # This is a simplified approach - in a real implementation, we would need a more robust way to find the element
    elements = soup.find_all(tag_name)
    if not elements:
        return None

    # Extract class information if available
    class_match = re.search(r'class="([^"]*)"', element_str)
    class_names = class_match.group(1).split() if class_match else []

    # Find elements with matching classes
    matching_elements = []
    for element in elements:
        if class_names:
            element_classes = element.get("class", [])
            if all(cls in element_classes for cls in class_names):
                matching_elements.append(element)
        else:
            # If no class to match, just use the first element of the tag type
            matching_elements.append(element)
            break

    if not matching_elements:
        return None

    # Apply contrast fix to all matching elements
    for element in matching_elements:
        # Determine if we should adjust text color or background color
        # For simplicity, we'll always adjust text color to black or white

        # Check if the element has inline style with background-color
        style = element.get("style", "")
        bg_color_match = re.search(r"background-color:\s*([^;]+)", style)

        if bg_color_match:
            bg_color = bg_color_match.group(1).strip().lower()

            # Determine if background is light or dark (simplified)
            is_dark_bg = _is_dark_color(bg_color)

            # Set text color based on background
            new_color = "#FFFFFF" if is_dark_bg else "#000000"

            # Update or add color to style
            if "color:" in style:
                style = re.sub(r"color:\s*[^;]+", f"color: {new_color}", style)
            else:
                style += f"; color: {new_color}"

            element["style"] = style
            return f"Adjusted text color to {new_color} for better contrast"

        # If no background color in style, check for text color
        color_match = re.search(r"color:\s*([^;]+)", style)
        if color_match:
            text_color = color_match.group(1).strip().lower()

            # Determine if text is light or dark (simplified)
            is_dark_text = _is_dark_color(text_color)

            # Set background color based on text
            new_bg_color = "#000000" if is_dark_text else "#FFFFFF"

            # Update or add background-color to style
            if "background-color:" in style:
                style = re.sub(
                    r"background-color:\s*[^;]+",
                    f"background-color: {new_bg_color}",
                    style,
                )
            else:
                style += f"; background-color: {new_bg_color}"

            element["style"] = style
            return f"Adjusted background color to {new_bg_color} for better contrast"

        # If no inline styles, add them
        element["style"] = "color: #000000; background-color: #FFFFFF"
        return "Added high contrast colors (black text on white background)"

    return None


def _is_dark_color(color: str) -> bool:
    """
    Determine if a color is dark or light.

    Args:
        color: CSS color value

    Returns:
        True if the color is dark, False if it's light
    """
    # Handle hex colors
    if color.startswith("#"):
        if len(color) == 4:  # Short hex (#RGB)
            r = int(color[1] + color[1], 16)
            g = int(color[2] + color[2], 16)
            b = int(color[3] + color[3], 16)
        elif len(color) == 7:  # Full hex (#RRGGBB)
            r = int(color[1:3], 16)
            g = int(color[3:5], 16)
            b = int(color[5:7], 16)
        else:
            return False  # Invalid hex

    # Handle rgb/rgba colors
    elif color.startswith("rgb"):
        rgb_match = re.search(r"rgba?\((\d+),\s*(\d+),\s*(\d+)", color)
        if rgb_match:
            r = int(rgb_match.group(1))
            g = int(rgb_match.group(2))
            b = int(rgb_match.group(3))
        else:
            return False  # Invalid rgb

    # Handle named colors (simplified)
    elif color in [
        "black",
        "darkblue",
        "darkgreen",
        "darkred",
        "navy",
        "purple",
        "brown",
    ]:
        return True
    # elif color in ['white', 'yellow', 'lime', 'cyan', 'pink', 'lightblue', 'lightgreen']:
    #     return False
    else:
        return False  # Unknown color

    # Calculate perceived brightness
    # Formula: (0.299*R + 0.587*G + 0.114*B)
    brightness = (0.299 * r + 0.587 * g + 0.114 * b) / 255

    # Return True if dark (brightness < 0.5)
    return brightness < 0.5


def remediate_insufficient_color_contrast_ai(
    soup: BeautifulSoup, issue: Dict[str, Any], bedrock_client=None, brand_colors: Optional[Dict[str, str]] = None
) -> Optional[str]:
    """
    Remediate insufficient color contrast using AI to suggest accessible alternatives.

    This function uses AI to generate color suggestions that maintain brand identity
    while ensuring WCAG compliance.

    Args:
        soup: The BeautifulSoup object representing the HTML document
        issue: The accessibility issue to remediate
        bedrock_client: Optional BedrockClient instance for AI-powered suggestions
        brand_colors: Optional dict of brand colors (e.g., {'primary': '#1E3A8A', 'secondary': '#F59E0B'})

    Returns:
        A message describing the remediation, or None if no remediation was performed
    """
    # Extract issue information
    location = issue.get('location', {})
    text_color = location.get('text_color', '#000000')
    bg_color = location.get('background_color', '#FFFFFF')
    contrast_ratio = location.get('contrast_ratio', '1:1')
    required_ratio = location.get('required_ratio_aa', '4.5:1')
    is_large_text = location.get('is_large_text', False)

    logger.info(
        f"Remediating color contrast: current={contrast_ratio}, required={required_ratio}, "
        f"text={text_color}, bg={bg_color}, large_text={is_large_text}"
    )

    # If no Bedrock client, fall back to programmatic fix
    if not bedrock_client:
        logger.debug("No Bedrock client provided, using programmatic fix")
        return remediate_insufficient_color_contrast(soup, issue)

    try:
        # Generate AI-powered color suggestion
        suggested_colors = suggest_accessible_colors_ai(
            bedrock_client=bedrock_client,
            current_text_color=text_color,
            current_bg_color=bg_color,
            required_ratio=required_ratio,
            is_large_text=is_large_text,
            brand_colors=brand_colors
        )

        if suggested_colors:
            new_text_color, new_bg_color = suggested_colors

            # Apply the AI-suggested colors
            element_str = issue.get("element", "")
            if not element_str:
                return None

            # Find and update the element
            tag_match = re.match(r"<([a-zA-Z0-9]+)", element_str)
            if not tag_match:
                return None

            tag_name = tag_match.group(1)
            elements = soup.find_all(tag_name)

            if elements:
                element = elements[0]  # Simplified: update first matching element
                style = element.get("style", "")

                # Update colors
                if "color:" in style:
                    style = re.sub(r"color:\s*[^;]+", f"color: {new_text_color}", style)
                else:
                    style += f"; color: {new_text_color}"

                if "background-color:" in style:
                    style = re.sub(r"background-color:\s*[^;]+", f"background-color: {new_bg_color}", style)
                else:
                    style += f"; background-color: {new_bg_color}"

                element["style"] = style

                return f"AI-suggested colors applied: text={new_text_color}, background={new_bg_color}"

    except Exception as e:
        logger.warning(f"AI color remediation failed: {e}, falling back to programmatic fix")
        return remediate_insufficient_color_contrast(soup, issue)

    return None


def suggest_accessible_colors_ai(
    bedrock_client,
    current_text_color: str,
    current_bg_color: str,
    required_ratio: str,
    is_large_text: bool = False,
    brand_colors: Optional[Dict[str, str]] = None
) -> Optional[Tuple[str, str]]:
    """
    Use AI to suggest accessible color combinations.

    Args:
        bedrock_client: BedrockClient instance
        current_text_color: Current text color (hex)
        current_bg_color: Current background color (hex)
        required_ratio: Required contrast ratio (e.g., '4.5:1')
        is_large_text: Whether the text is large
        brand_colors: Optional brand color palette

    Returns:
        Tuple of (suggested_text_color, suggested_bg_color) or None
    """
    try:
        # Build prompt for AI
        brand_info = ""
        if brand_colors:
            brand_info = f"\n\nBrand colors to consider: {', '.join([f'{k}: {v}' for k, v in brand_colors.items()])}"
            brand_info += "\nPlease try to maintain brand identity while ensuring accessibility."

        prompt = f"""You are an accessibility expert helping to fix color contrast issues.

Current situation:
- Text color: {current_text_color}
- Background color: {current_bg_color}
- Required contrast ratio: {required_ratio}
- Text size: {'Large (18pt+)' if is_large_text else 'Normal'}{brand_info}

Task: Suggest TWO accessible color combinations that meet WCAG {required_ratio} contrast requirements:
1. A minimal change approach (adjust only one color slightly)
2. A high-contrast approach (if minimal change isn't sufficient)

For each suggestion, provide:
- Text color (hex code)
- Background color (hex code)
- Brief explanation

Format your response as:
Option 1:
Text: #RRGGBB
Background: #RRGGBB
Explanation: ...

Option 2:
Text: #RRGGBB
Background: #RRGGBB
Explanation: ...

Choose colors that:
- Meet the required contrast ratio
- Maintain readability
- Preserve design intent when possible
- Work well with the content context
"""

        # Call Bedrock
        response = bedrock_client.generate_text(
            prompt=prompt,
            purpose='color_contrast_remediation',
            max_tokens=300
        )

        if response:
            # Parse the AI response
            colors = parse_color_suggestions(response)
            if colors:
                logger.info(f"AI suggested colors: {colors}")
                # Return the first (minimal change) option
                return colors[0]

    except Exception as e:
        logger.warning(f"Failed to get AI color suggestions: {e}")

    return None


def parse_color_suggestions(ai_response: str) -> Optional[list]:
    """
    Parse AI response to extract color suggestions.

    Args:
        ai_response: The AI-generated response text

    Returns:
        List of tuples [(text_color, bg_color), ...]
    """
    suggestions = []

    # Pattern to match color suggestions
    option_pattern = r'Option \d+:.*?Text:\s*(#[0-9A-Fa-f]{6}).*?Background:\s*(#[0-9A-Fa-f]{6})'

    matches = re.finditer(option_pattern, ai_response, re.DOTALL | re.IGNORECASE)

    for match in matches:
        text_color = match.group(1).upper()
        bg_color = match.group(2).upper()
        suggestions.append((text_color, bg_color))

    return suggestions if suggestions else None


def calculate_contrast_ratio(color1: str, color2: str) -> float:
    """
    Calculate WCAG contrast ratio between two colors.

    Args:
        color1: First color (hex)
        color2: Second color (hex)

    Returns:
        Contrast ratio as float
    """
    # Convert hex to RGB
    def hex_to_rgb(hex_color):
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    # Calculate relative luminance
    def relative_luminance(rgb):
        r, g, b = [x / 255.0 for x in rgb]

        def adjust(c):
            return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

        r, g, b = adjust(r), adjust(g), adjust(b)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    l1 = relative_luminance(hex_to_rgb(color1))
    l2 = relative_luminance(hex_to_rgb(color2))

    # Calculate ratio
    if l1 > l2:
        return (l1 + 0.05) / (l2 + 0.05)
    else:
        return (l2 + 0.05) / (l1 + 0.05)


def adjust_color_for_contrast(
    text_color: str,
    bg_color: str,
    target_ratio: float = 4.5,
    adjust_text: bool = True
) -> str:
    """
    Programmatically adjust a color to meet contrast requirements.

    Args:
        text_color: Text color (hex)
        bg_color: Background color (hex)
        target_ratio: Target contrast ratio
        adjust_text: If True, adjust text color; if False, adjust background

    Returns:
        Adjusted color (hex)
    """
    # This is a simplified algorithmic approach
    # In a full implementation, would iteratively adjust until target is met

    color_to_adjust = text_color if adjust_text else bg_color
    fixed_color = bg_color if adjust_text else text_color

    # Get luminance of fixed color
    def hex_to_rgb(hex_color):
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    def relative_luminance(rgb):
        r, g, b = [x / 255.0 for x in rgb]
        def adjust(c):
            return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
        r, g, b = adjust(r), adjust(g), adjust(b)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    fixed_luminance = relative_luminance(hex_to_rgb(fixed_color))

    # Determine if we need lighter or darker
    if fixed_luminance < 0.5:
        # Dark background, need light text
        return '#FFFFFF'
    else:
        # Light background, need dark text
        return '#000000'
