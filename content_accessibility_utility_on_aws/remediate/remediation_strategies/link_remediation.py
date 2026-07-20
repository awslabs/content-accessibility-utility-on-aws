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


def _domain_of(url: str) -> Optional[str]:
    """
    Extract the bare domain (no scheme, no leading ``www.``) from an http(s)
    URL, or None if it is not an http(s) URL. Shared by the link strategies so
    their URL-to-label heuristics cannot drift apart.
    """
    match = re.search(r"https?://(?:www\.)?([^/]+)", url or "")
    return match.group(1) if match else None


def _set_link_text(link, new_text: str) -> None:
    """Set an anchor's accessible text without destroying nested markup.

    Assigning ``link.string`` replaces *all* children, which silently discards
    nested elements such as icons (``<i>``) or images inside the anchor. To
    preserve them, this replaces only the anchor's own text nodes with the new
    text, and — when the anchor has no direct text node to replace (e.g. it
    contains only an ``<img>``) — appends a screen-reader-only span so the link
    gets an accessible name while its visual content stays intact.
    """
    from bs4 import NavigableString

    text_nodes = [c for c in link.contents if isinstance(c, NavigableString) and c.strip()]
    has_child_tags = any(getattr(c, "name", None) for c in link.contents)

    if not has_child_tags:
        # Plain text link: safe to replace wholesale.
        link.string = new_text
        return

    if text_nodes:
        # Replace the first meaningful text node; blank out any others.
        text_nodes[0].replace_with(new_text)
        for extra in text_nodes[1:]:
            extra.replace_with("")
        return

    # Only non-text children (e.g. an <img>): add sr-only text, keep the markup.
    # Walk up to the BeautifulSoup document, which owns new_tag().
    root = link
    while root.parent is not None:
        root = root.parent
    if hasattr(root, "new_tag"):
        sr = root.new_tag("span")
        sr["class"] = "sr-only"
        sr.string = new_text
        link.append(sr)
    else:  # pragma: no cover - defensive
        link.append(new_text)


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
    domain = _domain_of(href)
    if domain:
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
    domain = _domain_of(href)
    if domain:
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
    domain = _domain_of(url_text)
    if domain:
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


def remediate_duplicate_link_text(
    soup: BeautifulSoup, issue: Dict[str, Any], *args
) -> Optional[str]:
    """
    Disambiguate links that share the same text but point to different URLs.

    WCAG 2.4.9: when several links read the same (e.g. two "click here" links
    going to different destinations), a user cannot tell them apart out of
    context. There is no mechanical rewrite for this — the fix depends on what
    each destination *is*, which is exactly the kind of judgment the model layer
    is for. This strategy rewrites the specific link the issue points at with
    descriptive text derived from that link's own destination and surrounding
    text, so each formerly-identical link ends up distinct and meaningful.

    Falls back (no model / no context) to appending the destination domain to
    the existing text, which still makes same-text links distinguishable.

    Args:
        soup: The BeautifulSoup document.
        issue: The accessibility issue (points at one of the duplicate links).
        *args: Optional BedrockClient used to author the descriptive text.

    Returns:
        A message describing the remediation, or None if it could not be applied.
    """
    bedrock_client = args[0] if args else None

    link, href = _resolve_link(soup, issue)
    if link is None:
        return None

    current_text = link.get_text(strip=True)

    # An earlier strategy (e.g. generic-link-text) may have already rewritten
    # this link so it no longer collides with its former twins. If no other link
    # on the page still shares this exact text, the ambiguity is already
    # resolved — report success rather than a spurious failure.
    same_text_siblings = [
        a for a in soup.find_all("a")
        if a is not link and a.get_text(strip=True).lower() == current_text.lower()
    ]
    if not same_text_siblings:
        return f"Link text '{current_text}' is already unique; no change needed"

    # Prefer model-authored descriptive text grounded in this link's own
    # destination and the sentence around it, so the two same-text links diverge
    # into meaningful, distinct labels.
    parent = link.find_parent(["p", "li", "td", "div"])
    surrounding = parent.get_text(separator=" ", strip=True) if parent else ""
    generated = generate_short_text(
        bedrock_client,
        instruction=(
            "Several links on this page share the same text but go to different "
            "places, which is ambiguous. Rewrite this one link's text into "
            "descriptive text (2-6 words) that uniquely says where THIS link "
            f"goes. Do not reuse the current generic text. The link points to: {href}"
        ),
        context=(
            f"Current (ambiguous) link text: '{current_text}'\n"
            f"This link's destination: {href}\n"
            f"Surrounding text: {surrounding}"
        ),
        purpose="link_text_generation",
        max_words=8,
    )
    if generated and generated.lower() != current_text.lower():
        _set_link_text(link, generated)
        return (
            f"Disambiguated duplicate link text '{current_text}' -> '{generated}'"
        )

    # Fallback: append a destination hint so same-text links differ. Prefer the
    # most specific stable part of the URL that is NOT already in the text. The
    # bare domain alone does not distinguish same-host/different-path links
    # (e.g. x.com/a vs x.com/b), so try a path segment first, then the domain.
    path_hint = (href or "").strip("/").split("/")[-1].replace("-", " ").replace("_", " ")
    domain = _domain_of(href)
    for hint in (path_hint, domain):
        if hint and hint.lower() not in current_text.lower():
            new_text = f"{current_text} ({hint})" if current_text else f"Visit {hint}"
            _set_link_text(link, new_text)
            return f"Disambiguated duplicate link text with destination: {new_text}"

    return None
