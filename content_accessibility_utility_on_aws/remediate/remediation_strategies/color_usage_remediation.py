# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Color usage remediation strategies.

This module provides remediation strategies for color-only indication issues (WCAG 1.4.1).
Ensures information is conveyed through multiple means, not just color.
"""

from typing import Dict, Any, Optional
from bs4 import BeautifulSoup, Tag
import re
import logging

from content_accessibility_utility_on_aws.utils.logging_helper import setup_logger

logger = setup_logger(__name__)


def remediate_color_only_indication(
    soup: BeautifulSoup, issue: Dict[str, Any]
) -> Optional[str]:
    """
    Remediate color-only indication issues by adding non-color indicators.

    Args:
        soup: The BeautifulSoup object representing the HTML document
        issue: The accessibility issue to remediate

    Returns:
        A message describing the remediation, or None if no remediation was performed
    """
    location = issue.get('location', {})
    pattern = location.get('pattern', '')

    logger.info(f"Remediating color-only indication: pattern={pattern}")

    # Route to specific remediation based on pattern
    if pattern == 'required_field_indicator':
        return remediate_required_field_indicator(soup, issue)
    elif pattern == 'link_without_underline':
        return remediate_link_without_underline(soup, issue)
    elif pattern == 'form_validation_error':
        return remediate_form_validation_error(soup, issue)
    elif pattern == 'status_badge':
        return remediate_status_badge(soup, issue)
    else:
        logger.warning(f"Unknown color-only pattern: {pattern}")
        return None


def remediate_required_field_indicator(
    soup: BeautifulSoup, issue: Dict[str, Any]
) -> Optional[str]:
    """
    Add required attribute and/or visible text label to required fields.

    Args:
        soup: The BeautifulSoup object
        issue: The accessibility issue

    Returns:
        Description of remediation
    """
    # Find the element
    element = _find_element_from_issue(soup, issue)
    if not element:
        return None

    # Add required attribute if it's an input
    if element.name in ['input', 'select', 'textarea']:
        # Add required attribute
        if not element.get('required'):
            element['required'] = ''

        # Add aria-required for better screen reader support
        if not element.get('aria-required'):
            element['aria-required'] = 'true'

        # Find associated label
        element_id = element.get('id')
        label = None

        if element_id:
            label = soup.find('label', attrs={'for': element_id})

        if not label:
            label = element.find_parent('label')

        # Add text indicator to label
        if label:
            # Check if label already has "required" text
            label_text = label.get_text().lower()
            if 'required' not in label_text and '*' not in label_text:
                # Add " (required)" text
                # Find the last text node in label
                if label.string:
                    label.string = label.string.strip() + ' (required)'
                else:
                    # Label has child elements, append to last text
                    label.append(' (required)')

        return "Added 'required' attribute, aria-required, and visible '(required)' text label"

    return None


def remediate_link_without_underline(
    soup: BeautifulSoup, issue: Dict[str, Any]
) -> Optional[str]:
    """
    Add text-decoration underline to links that rely on color alone.

    Args:
        soup: The BeautifulSoup object
        issue: The accessibility issue

    Returns:
        Description of remediation
    """
    element = _find_element_from_issue(soup, issue)
    if not element or element.name != 'a':
        return None

    # Add underline via inline style
    style = element.get('style', '')

    # Check if text-decoration already exists
    if 'text-decoration' not in style:
        # Add underline
        if style and not style.strip().endswith(';'):
            style += '; '
        style += 'text-decoration: underline;'
        element['style'] = style

        return "Added text-decoration underline to distinguish link from surrounding text"
    else:
        # Update existing text-decoration to include underline
        style = re.sub(
            r'text-decoration:\s*([^;]+)',
            lambda m: f'text-decoration: underline' if 'none' in m.group(1) else m.group(0),
            style
        )
        element['style'] = style

        return "Updated text-decoration to underline"

    return None


def remediate_form_validation_error(
    soup: BeautifulSoup, issue: Dict[str, Any]
) -> Optional[str]:
    """
    Add ARIA attributes and/or error icon to validation messages.

    Args:
        soup: The BeautifulSoup object
        issue: The accessibility issue

    Returns:
        Description of remediation
    """
    element = _find_element_from_issue(soup, issue)
    if not element:
        return None

    remediations = []

    # Add role="alert" for screen readers
    if not element.get('role'):
        element['role'] = 'alert'
        remediations.append("Added role='alert'")

    # Add aria-live="polite" for dynamic errors
    if not element.get('aria-live'):
        element['aria-live'] = 'polite'
        remediations.append("Added aria-live='polite'")

    # Add error text prefix if not present
    error_text = element.get_text().strip()
    if error_text and not any(word in error_text.lower() for word in ['error', 'invalid', 'required']):
        # Prepend "Error: " to the text
        if element.string:
            element.string = f"Error: {element.string}"
            remediations.append("Added 'Error:' prefix to text")
        else:
            # Has child elements, insert text at beginning
            new_text = soup.new_string("Error: ")
            element.insert(0, new_text)
            remediations.append("Added 'Error:' prefix to text")

    # Add error icon (using Unicode symbol)
    # Check if element already has an icon
    has_icon = element.find(['i', 'svg', 'img']) is not None

    if not has_icon:
        # Add a text-based icon at the start
        icon_span = soup.new_tag('span', attrs={'aria-hidden': 'true'})
        icon_span.string = '⚠ '  # Warning symbol
        element.insert(0, icon_span)
        remediations.append("Added warning icon")

    if remediations:
        return '; '.join(remediations)

    return None


def remediate_status_badge(
    soup: BeautifulSoup, issue: Dict[str, Any]
) -> Optional[str]:
    """
    Add explicit text or icon to status badges that rely on color alone.

    Args:
        soup: The BeautifulSoup object
        issue: The accessibility issue

    Returns:
        Description of remediation
    """
    element = _find_element_from_issue(soup, issue)
    if not element:
        return None

    # Get background color to determine status type
    location = issue.get('location', {})
    bg_color = location.get('background_color', '')

    # Determine status type from color
    status_type = _infer_status_from_color(bg_color)

    # Get current text
    current_text = element.get_text().strip()

    # If text is very short or generic, add explicit status
    if len(current_text) < 3 or current_text.lower() in ['ok', 'no', 'yes']:
        # Map status to explicit text
        status_text_map = {
            'success': 'Success',
            'error': 'Error',
            'warning': 'Warning',
            'info': 'Info',
            'unknown': 'Status'
        }

        new_text = status_text_map.get(status_type, 'Status')

        # Replace or append text
        if current_text:
            element.string = f"{new_text}: {current_text}"
        else:
            element.string = new_text

        return f"Added explicit '{new_text}' text to status badge"

    # Add status icon
    icon_map = {
        'success': '✓',  # Check mark
        'error': '✗',     # X mark
        'warning': '⚠',   # Warning
        'info': 'ℹ',      # Info
        'unknown': '•'    # Bullet
    }

    icon = icon_map.get(status_type, '•')

    # Check if icon already exists
    if icon not in current_text:
        icon_span = soup.new_tag('span', attrs={'aria-hidden': 'true'})
        icon_span.string = f"{icon} "
        element.insert(0, icon_span)

        return f"Added {status_type} icon to status badge"

    return None


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


def _infer_status_from_color(hex_color: str) -> str:
    """
    Infer status type from background color.

    Args:
        hex_color: Hex color code

    Returns:
        Status type ('success', 'error', 'warning', 'info', 'unknown')
    """
    if not hex_color or hex_color == 'transparent':
        return 'unknown'

    try:
        # Remove # and convert to RGB
        hex_color = hex_color.lstrip('#')
        if len(hex_color) != 6:
            return 'unknown'

        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)

        # Classify based on dominant color
        # Green dominant = success
        if g > r and g > b and g > 100:
            return 'success'

        # Red dominant = error
        if r > g and r > b and r > 100:
            return 'error'

        # Yellow/Orange = warning
        if r > 150 and g > 100 and b < 100:
            return 'warning'

        # Blue dominant = info
        if b > r and b > g and b > 100:
            return 'info'

    except (ValueError, TypeError):
        pass

    return 'unknown'


def remediate_color_only_indication_ai(
    soup: BeautifulSoup, issue: Dict[str, Any], bedrock_client=None
) -> Optional[str]:
    """
    Use AI to suggest comprehensive remediation for color-only issues.

    This can provide context-aware suggestions for adding icons, text, or ARIA attributes.

    Args:
        soup: The BeautifulSoup object
        issue: The accessibility issue
        bedrock_client: Optional BedrockClient for AI suggestions

    Returns:
        Description of remediation
    """
    # For now, fall back to programmatic remediation
    # In a full implementation, AI could analyze context and suggest better text/icons
    return remediate_color_only_indication(soup, issue)
