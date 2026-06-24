# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Link accessibility remediation strategies.

This module provides remediation strategies for link-related accessibility issues.
"""

from typing import Dict, Any, Optional
from bs4 import BeautifulSoup
import re

from content_accessibility_utility_on_aws.remediate.helpers.text_generation import (
    generate_short_text,
)
from content_accessibility_utility_on_aws.remediate.helpers.selector_helper import (
    find_element_from_issue,
)


def _resolve_link(soup: BeautifulSoup, issue: Dict[str, Any]):
    """
    Resolve the anchor element an issue refers to.

    Uses the shared issue resolver (which matches the auditor's recorded CSS
    path) and confirms the result is an anchor, returning it together with its
    href. Returns (None, None) when no matching link is found.
    """
    element = find_element_from_issue(soup, issue)
    if element is None or element.name != "a":
        return None, None
    return element, element.get("href", "")


def remediate_empty_link_text(
    soup: BeautifulSoup, issue: Dict[str, Any], *args
) -> Optional[str]:
    """
    Remediate empty link text by adding descriptive text based on context.

    Args:
        soup: The BeautifulSoup object representing the HTML document
        issue: The accessibility issue to remediate

    Returns:
        A message describing the remediation, or None if no remediation was performed
    """
    empty_link, href = _resolve_link(soup, issue)
    if empty_link is None:
        return None

    # Only act if the link really has no text content.
    if empty_link.get_text(strip=True):
        return None

    # Generate descriptive text based on the URL
    if href and href.startswith("http"):
        # Extract domain name
        domain_match = re.search(r"https?://(?:www\.)?([^/]+)", href)
        if domain_match:
            domain = domain_match.group(1)
            empty_link.string = f"Link to {domain}"
            return f"Added text to empty link: Link to {domain}"

    # Default text
    empty_link.string = f"Link to {href}"
    return f"Added text to empty link: Link to {href}"


def remediate_generic_link_text(
    soup: BeautifulSoup, issue: Dict[str, Any], *args
) -> Optional[str]:
    """
    Remediate generic link text by adding more descriptive text based on context.

    Args:
        soup: The BeautifulSoup object representing the HTML document
        issue: The accessibility issue to remediate
        *args: Optional BedrockClient used to derive descriptive link text

    Returns:
        A message describing the remediation, or None if no remediation was performed
    """
    bedrock_client = args[0] if args else None

    generic_link, href = _resolve_link(soup, issue)
    if generic_link is None:
        return None

    # Confirm the link text is actually generic before rewriting it.
    generic_texts = [
        "click here",
        "here",
        "read more",
        "more",
        "learn more",
        "details",
        "link",
    ]
    current_text = generic_link.get_text(strip=True)
    if current_text.lower() not in generic_texts:
        return None

    # Prefer model-generated descriptive text using the link's destination and
    # the surrounding sentence as context. Falls back to the heuristics below.
    parent = generic_link.find_parent(["p", "li", "td", "div"])
    surrounding = parent.get_text(separator=" ", strip=True) if parent else ""
    generated = generate_short_text(
        bedrock_client,
        instruction=(
            "Rewrite the generic link text into descriptive link text (2-6 words) "
            "that states where the link goes. Do not use phrases like 'click "
            f"here'. The link points to: {href}"
        ),
        context=f"Generic link text: '{current_text}'\nSurrounding text: {surrounding}",
        purpose="link_text_generation",
        max_words=8,
    )
    if generated:
        generic_link.string = generated
        return f"Replaced generic link text '{current_text}' with: {generated}"

    # Generate better text based on the URL and context
    if href and href.startswith("http"):
        # Extract domain name
        domain_match = re.search(r"https?://(?:www\.)?([^/]+)", href)
        if domain_match:
            domain = domain_match.group(1)
            generic_link.string = f"Visit {domain} website"
            return f"Replaced generic link text with: Visit {domain} website"

    # Try to get context from surrounding text
    parent = generic_link.parent
    if parent and parent.name != "body":
        parent_text = parent.get_text(strip=True)
        # Remove the link text from parent text
        context_text = parent_text.replace(current_text, "").strip()
        if context_text:
            # Use first 30 chars of context
            context_preview = context_text[:30].strip()
            if len(context_text) > 30:
                context_preview += "..."
            generic_link.string = f"More about {context_preview}"
            return (
                f"Replaced generic link text with context: More about {context_preview}"
            )

    # Default improvement (current_text captured above)
    if current_text.lower() == "click here":
        generic_link.string = "View details"
    elif current_text.lower() == "read more":
        generic_link.string = "Read more about this topic"
    elif current_text.lower() == "learn more":
        generic_link.string = "Learn more about this topic"
    else:
        generic_link.string = "View related information"

    return f"Replaced generic link text '{current_text}' with more descriptive text"


def remediate_url_as_link_text(
    soup: BeautifulSoup, issue: Dict[str, Any], *args
) -> Optional[str]:
    """
    Remediate URL as link text by replacing it with more descriptive text.

    Args:
        soup: The BeautifulSoup object representing the HTML document
        issue: The accessibility issue to remediate

    Returns:
        A message describing the remediation, or None if no remediation was performed
    """
    url_link, _ = _resolve_link(soup, issue)
    if url_link is None:
        return None

    # Confirm the link text really is a bare URL.
    url_text = url_link.get_text(strip=True)
    if not url_text.startswith(("http://", "https://", "www.")):
        return None

    # Extract domain name
    domain_match = re.search(r"https?://(?:www\.)?([^/]+)", url_text)
    if domain_match:
        domain = domain_match.group(1)
        url_link.string = f"Visit {domain}"
        return f"Replaced URL with domain name: Visit {domain}"

    # Default text
    url_link.string = "Visit website"
    return "Replaced URL with generic description"


def remediate_new_window_link_no_warning(
    soup: BeautifulSoup, issue: Dict[str, Any], *args
) -> Optional[str]:
    """
    Remediate links that open in new windows without warning by adding a warning.

    Args:
        soup: The BeautifulSoup object representing the HTML document
        issue: The accessibility issue to remediate

    Returns:
        A message describing the remediation, or None if no remediation was performed
    """
    link, _ = _resolve_link(soup, issue)
    if link is None:
        return None

    # Only act on links that actually open in a new window.
    if link.get("target") != "_blank":
        return None

    # Skip if it already warns about the new window.
    text = link.get_text(strip=True)
    if "new window" in text.lower() or "new tab" in text.lower():
        return None

    # Add screen reader text
    sr_span = soup.new_tag("span")
    sr_span["class"] = "sr-only"
    sr_span.string = " (opens in new window)"
    link.append(sr_span)

    # Add title attribute if not present
    if not link.get("title"):
        link["title"] = f"{text} (opens in new window)"

    return "Added screen reader text and title to indicate link opens in new window"
