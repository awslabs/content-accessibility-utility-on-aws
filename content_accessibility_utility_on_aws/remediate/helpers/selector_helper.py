# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Selector Helper module.

This module provides functionality to generate and manipulate CSS selectors
for HTML elements.
"""

import re
from typing import Any, Dict, Optional
from bs4 import BeautifulSoup, Tag

from content_accessibility_utility_on_aws.utils.logging_helper import setup_logger

# Set up module-level logger
logger = setup_logger(__name__)


def find_element_from_issue(
    soup: BeautifulSoup, issue: Dict[str, Any]
) -> Optional[Tag]:
    """
    Resolve the HTML element an accessibility issue refers to.

    The auditor records ``issue["location"]["path"]`` as a precise CSS selector
    (built by ``AccessibilityAuditor._get_element_path``, including
    ``:nth-of-type`` disambiguation), so the path is the canonical way to find
    the exact element even when several elements share a tag name. The auditor
    prefixes the path with the BeautifulSoup root token ``[document]``, which is
    not a valid selector, so it is stripped before matching.

    As a secondary fallback, when ``issue["element"]`` happens to contain element
    HTML (rather than just the tag name the auditor normally stores), an
    anchor's ``href`` is used to locate it.

    Args:
        soup: The parsed HTML document.
        issue: The accessibility issue, which may carry ``location.path`` and/or
            ``element``.

    Returns:
        The matching element, or None if it cannot be resolved.
    """
    location = issue.get("location") or {}
    path = location.get("path")
    if path:
        # Drop the synthetic BeautifulSoup root token and any empty segments.
        selector = " > ".join(
            seg for seg in path.split(" > ") if seg and seg != "[document]"
        )
        if selector:
            try:
                element = soup.select_one(selector)
            except Exception as e:
                logger.debug(f"Could not resolve issue path '{selector}': {e}")
                element = None
            if element is not None:
                return element

    # The audit-time path can be invalidated when earlier remediations inject
    # elements (e.g. skip links, landmarks) and shift positional/nth-of-type
    # selectors. Fall back to matching an anchor by its recorded href, which is
    # stable across such mutations.
    href = _recorded_href(issue)
    if href:
        candidates = soup.find_all("a", href=href)
        if candidates:
            return candidates[0]

    return None


def _recorded_href(issue: Dict[str, Any]) -> Optional[str]:
    """
    Extract the anchor href recorded on an issue, if any.

    Checks, in order: an element string that is HTML, the context's recorded
    attributes, and the context's html_snippet.
    """
    element_str = issue.get("element", "")
    if isinstance(element_str, str) and element_str.lstrip().startswith("<a "):
        match = re.search(r'href="([^"]*)"', element_str)
        if match:
            return match.group(1)

    context = issue.get("context") or {}
    if isinstance(context, dict):
        attrs = context.get("attributes")
        if isinstance(attrs, dict) and attrs.get("href"):
            return attrs["href"]

        snippet = context.get("html_snippet")
        if isinstance(snippet, str):
            match = re.search(r'href="([^"]*)"', snippet)
            if match:
                return match.group(1)

    return None


class SelectorHelper:
    """
    Class for generating and manipulating CSS selectors for HTML elements.
    """

    @staticmethod
    def generate_selector(
        element_html: str, context_html: Optional[str] = None
    ) -> Optional[str]:
        """
        Generate a CSS selector for an HTML element.

        Args:
            element_html: HTML of the element
            context_html: HTML context surrounding the element

        Returns:
            CSS selector or None if not possible
        """
        try:
            # Parse the element HTML
            soup = BeautifulSoup(element_html, "html.parser")
            element = soup.find()

            if not element:
                return None

            # Start with the tag name
            selector = element.name

            # Add ID if available
            if element.get("id"):
                selector = f"{selector}#{element['id']}"
                return selector

            # Add classes if available
            if element.get("class"):
                classes = ".".join(element["class"])
                selector = f"{selector}.{classes}"
                return selector

            # Add data attributes if available
            for attr in element.attrs:
                if attr.startswith("data-"):
                    selector = f"{selector}[{attr}='{element[attr]}']"
                    return selector

            # For images, use src attribute
            if element.name == "img" and element.get("src"):
                src = element["src"].split("/")[-1]  # Just use filename
                selector = f"{selector}[src$='{src}']"
                return selector

            # If we have context, try to create a more specific selector
            if context_html:
                context_soup = BeautifulSoup(context_html, "html.parser")
                parent = context_soup.find(element.name)

                if parent:
                    # Count siblings with same tag
                    siblings = parent.find_all(element.name)
                    if len(siblings) > 1:
                        # Find position of this element
                        for i, sibling in enumerate(siblings):
                            if str(sibling) == str(element):
                                selector = f"{selector}:nth-of-type({i+1})"
                                break

            return selector

        except Exception as e:
            logger.warning(f"Error generating selector: {e}")
            return None

    @staticmethod
    def get_element_by_selector(html: str, selector: str) -> Optional[BeautifulSoup]:
        """
        Get an element from HTML using a CSS selector.

        Args:
            html: HTML content
            selector: CSS selector

        Returns:
            BeautifulSoup element or None if not found
        """
        try:
            soup = BeautifulSoup(html, "html.parser")
            return soup.select_one(selector)
        except Exception as e:
            logger.warning(f"Error getting element by selector: {e}")
            return None

    @staticmethod
    def get_element_context(
        html: str, selector: str, context_size: int = 3
    ) -> Optional[str]:
        """
        Get the HTML context surrounding an element.

        Args:
            html: HTML content
            selector: CSS selector for the element
            context_size: Number of siblings to include before and after

        Returns:
            HTML context or None if element not found
        """
        try:
            soup = BeautifulSoup(html, "html.parser")
            element = soup.select_one(selector)

            if not element:
                return None

            # Get parent
            parent = element.parent

            # Get siblings
            siblings = list(parent.children)

            # Find index of element in siblings
            element_index = None
            for i, sibling in enumerate(siblings):
                if sibling is element:
                    element_index = i
                    break

            if element_index is None:
                return str(parent)

            # Get context range
            start = max(0, element_index - context_size)
            end = min(len(siblings), element_index + context_size + 1)

            # Create a new element with just the context
            context_soup = BeautifulSoup("<div></div>", "html.parser")
            context_div = context_soup.div

            # Add siblings in context range
            for i in range(start, end):
                context_div.append(siblings[i])

            return str(context_div)

        except Exception as e:
            logger.warning(f"Error getting element context: {e}")
            return None
