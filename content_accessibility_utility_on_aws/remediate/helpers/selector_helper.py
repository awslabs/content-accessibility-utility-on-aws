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

    **Resilience to DOM mutation.** Remediation applies fixes sequentially, and
    several of them restructure the tree — e.g. wrapping the body in ``<main>``
    or inserting ``<header>``/``<nav>``/skip links. That shifts the depth and
    ``:nth-of-type`` indices the audit-time path depends on, so a later issue's
    absolute path can silently resolve to nothing, and its fix is skipped. To
    stay correct regardless of remediation order, this resolver tries the exact
    path first and then falls back to identifiers that survive restructuring:
    recorded attributes (id/name/src/href/type/value), then the element's
    document-wide position among its tag, then its text content.

    Args:
        soup: The parsed HTML document.
        issue: The accessibility issue, which may carry ``location.path``,
            ``element``, and ``context`` (element_name/attributes/position/text).

    Returns:
        The matching element, or None if it cannot be resolved.
    """
    # 1. Exact path (fast, unambiguous when the tree is unchanged).
    element = _match_by_path(soup, issue)
    if element is not None:
        return element

    # 2. Recorded anchor href (stable across restructuring).
    href = _recorded_href(issue)
    if href:
        candidates = soup.find_all("a", href=href)
        if candidates:
            return candidates[0]

    # 3. Recorded distinctive attributes (id/name/src/type/value).
    element = _match_by_attributes(soup, issue)
    if element is not None:
        return element

    # 4. Recorded document-wide position among elements of the same tag.
    element = _match_by_position(soup, issue)
    if element is not None:
        return element

    # 5. Recorded text content (last resort, for text-bearing elements).
    element = _match_by_text(soup, issue)
    if element is not None:
        return element

    return None


def _match_by_path(soup: BeautifulSoup, issue: Dict[str, Any]) -> Optional[Tag]:
    """Resolve via the audit-time CSS path (root token stripped)."""
    location = issue.get("location") or {}
    path = location.get("path")
    if not path:
        return None
    selector = " > ".join(
        seg for seg in path.split(" > ") if seg and seg != "[document]"
    )
    if not selector:
        return None
    try:
        return soup.select_one(selector)
    except Exception as e:
        logger.debug(f"Could not resolve issue path '{selector}': {e}")
        return None


def _issue_context(issue: Dict[str, Any]) -> Dict[str, Any]:
    """Return the issue context dict (never None)."""
    context = issue.get("context")
    return context if isinstance(context, dict) else {}


def _recorded_tag(issue: Dict[str, Any]) -> Optional[str]:
    """The element's tag name, from context or the ``element`` field."""
    context = _issue_context(issue)
    name = context.get("element_name")
    if isinstance(name, str) and name:
        return name
    element_str = issue.get("element")
    # The auditor normally stores the bare tag name in ``element``.
    if isinstance(element_str, str) and element_str and "<" not in element_str:
        return element_str
    return None


def _match_by_attributes(soup: BeautifulSoup, issue: Dict[str, Any]) -> Optional[Tag]:
    """Match by distinctive recorded attributes, which survive restructuring.

    Uses the most specific stable attribute available. ``id`` is unique;
    ``name``/``src`` are usually unique for the tag; ``type``+``value`` narrows
    form controls. When a tag name is recorded the search is scoped to it.
    """
    context = _issue_context(issue)
    attrs = context.get("attributes")
    if not isinstance(attrs, dict) or not attrs:
        return None

    tag = _recorded_tag(issue)

    # id is unique by definition.
    if attrs.get("id"):
        found = soup.find(attrs=({"id": attrs["id"]}))
        if found is not None:
            return found

    # Try progressively less unique attribute combinations, scoped to the tag.
    for keys in (("name",), ("src",), ("type", "value"), ("type", "name")):
        if all(attrs.get(k) for k in keys):
            match_attrs = {k: attrs[k] for k in keys}
            candidates = soup.find_all(tag or True, attrs=match_attrs)
            if len(candidates) == 1:
                return candidates[0]
            # If multiple, fall through to position disambiguation below.
            if candidates:
                idx = _recorded_index(issue)
                if idx is not None:
                    same_tag = soup.find_all(candidates[0].name)
                    if 0 <= idx < len(same_tag) and same_tag[idx] in candidates:
                        return same_tag[idx]
                return candidates[0]
    return None


def _recorded_index(issue: Dict[str, Any]) -> Optional[int]:
    """The element's document-wide index among its tag (from context.position)."""
    position = _issue_context(issue).get("position")
    if isinstance(position, dict):
        idx = position.get("index")
        if isinstance(idx, int) and idx >= 0:
            return idx
    return None


def _match_by_position(soup: BeautifulSoup, issue: Dict[str, Any]) -> Optional[Tag]:
    """Match the Nth element of the recorded tag (document order).

    ``position.index`` from the audit is the element's index among all elements
    of its tag in the whole document. Wrapping/insertion of ancestor elements
    does not reorder elements of a given tag, so this index stays valid even
    when the ``:nth-of-type`` path does not.
    """
    tag = _recorded_tag(issue)
    idx = _recorded_index(issue)
    if not tag or idx is None:
        return None
    same_tag = soup.find_all(tag)
    if 0 <= idx < len(same_tag):
        return same_tag[idx]
    return None


def _match_by_text(soup: BeautifulSoup, issue: Dict[str, Any]) -> Optional[Tag]:
    """Match a text-bearing element of the recorded tag by exact text content."""
    context = _issue_context(issue)
    text = context.get("text_content")
    tag = _recorded_tag(issue)
    if not tag or not isinstance(text, str) or not text.strip():
        return None
    target = text.strip()
    for el in soup.find_all(tag):
        if el.get_text(strip=True) == target:
            return el
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
