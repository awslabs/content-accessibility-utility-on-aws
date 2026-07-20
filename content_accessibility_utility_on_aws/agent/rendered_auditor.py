# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Rendered auditor: the render-backed counterpart to ``AccessibilityAuditor``.

This runs the browser probe once over a page's HTML and returns issues in the
canonical dict shape, so the API layer can simply append them to the static
auditor's issue list (``audit_results["issues"] += rendered_issues``). It never
touches the static auditor or its hardcoded check list.

De-duplication: when a rendered finding and a static finding cover the same
node + criterion (contrast is the obvious case), the rendered finding is
authoritative because it reflects the real computed cascade. Callers pass the
static issues in so this class can drop the superseded static ones.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from content_accessibility_utility_on_aws.agent.axe_adapter import AxeAdapter
from content_accessibility_utility_on_aws.agent.browser_probe import (
    BrowserProbe,
    BrowserUnavailableError,
)
from content_accessibility_utility_on_aws.utils.logging_helper import setup_logger

logger = setup_logger(__name__)

# When a rendered issue on the same WCAG criterion exists for an element, these
# static issue types are considered superseded (the computed measurement wins).
_STATIC_SUPERSEDED_BY_RENDERED = {
    "1.4.3": {"insufficient-color-contrast", "potential-color-contrast-issue"},
}


def _normalize_path(path: Optional[str]) -> Optional[str]:
    """Normalize a ``location.path`` for cross-source comparison.

    The static auditor prefixes paths with the BeautifulSoup ``[document]`` root
    token; axe does not. Stripping it (the same way ``find_element_from_issue``
    resolves elements) lets an identical selector from either source compare
    equal. Selector *minimization* can still differ between the two engines, so
    this makes exact-selector matches de-duplicate reliably without claiming to
    reconcile every equivalent-but-differently-written selector.
    """
    if not path:
        return path
    return " > ".join(
        seg for seg in path.split(" > ") if seg and seg != "[document]"
    )


class RenderedAuditor:
    """Produce rendered/computed accessibility issues for HTML pages."""

    def __init__(self, probe: BrowserProbe) -> None:
        self.probe = probe

    def audit_html(self, html: str, page_number: int = 0) -> List[Dict[str, Any]]:
        """Render one page and return rendered issues in canonical shape.

        Returns an empty list (never raises) if the browser is unavailable, so
        the caller can degrade to static-only auditing.
        """
        try:
            probe_result = self.probe.render_and_probe(html)
        except BrowserUnavailableError as e:
            logger.warning("Rendered audit skipped, browser unavailable: %s", e)
            return []
        except Exception as e:  # pragma: no cover - defensive
            logger.warning("Rendered audit failed: %s", e)
            return []
        return AxeAdapter(page_number=page_number).to_issues(probe_result)

    @staticmethod
    def dedupe(
        static_issues: List[Dict[str, Any]],
        rendered_issues: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Drop static issues superseded by a rendered finding on the same node.

        Two issues collide when they resolve to the same element and WCAG
        criterion and the static type is in the superseded set for that
        criterion. The rendered issue is kept.

        Static and rendered selectors are written differently — the static
        auditor prefixes ``location.path`` with the BeautifulSoup ``[document]``
        root token (see ``_get_element_path``) while axe emits a bare CSS
        selector — so paths are normalized the same way ``find_element_from_issue``
        does before comparing, otherwise the keys would never match and nothing
        would ever be de-duplicated.
        """
        rendered_keys = {
            (_normalize_path(i["location"].get("path")), i["wcag_criterion"])
            for i in rendered_issues
        }
        kept: List[Dict[str, Any]] = []
        for issue in static_issues:
            crit = issue.get("wcag_criterion")
            path = _normalize_path((issue.get("location") or {}).get("path"))
            superseded_types = _STATIC_SUPERSEDED_BY_RENDERED.get(crit, set())
            if (
                issue.get("type") in superseded_types
                and (path, crit) in rendered_keys
            ):
                logger.debug(
                    "Dropping static issue %s superseded by rendered finding",
                    issue.get("type"),
                )
                continue
            kept.append(issue)
        return kept
