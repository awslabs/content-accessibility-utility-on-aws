# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Adapt browser-probe findings into the canonical accessibility issue dict.

The whole point of this layer plugging in cleanly is that it produces the exact
same issue shape the static auditor emits via
``AccessibilityAuditor._add_issue``. Downstream — report generation, grouping,
severity counts, and (crucially) remediation routing in ``RemediationManager``
— then works unchanged.

An issue dict looks like::

    {
      "id", "type", "wcag_criterion", "criterion_name", "criterion_level",
      "severity", "element", "description", "context",
      "location": {"path": "<css selector>", "page_number": N},
      "remediation_status", "remediation_source", "remediation_date",
    }

The routing key is ``type`` (hyphenated), and ``location.path`` must be a CSS
selector that ``find_element_from_issue`` can resolve with ``soup.select_one``.
axe conveniently emits exactly such a selector per node, so it maps straight in.
"""

from __future__ import annotations

from typing import Any, Dict, List

from content_accessibility_utility_on_aws.agent.browser_probe import ProbeResult
from content_accessibility_utility_on_aws.audit.standards import get_criterion_info

# Map an axe rule id to (issue_type, wcag_criterion, severity). Only rules that
# represent computed/rendered findings the static pipeline cannot make are
# included; rules that duplicate a static check are intentionally omitted so the
# two layers do not double-report (see de-dup in RenderedAuditor).
#
# ``issue_type`` uses the canonical hyphenated types the RemediationManager
# routes on. New interactive types are registered in that manager in Phase 0+.
AXE_RULE_MAP: Dict[str, Dict[str, str]] = {
    # Computed contrast — the static ColorContrastCheck only reads inline colors;
    # axe computes the real cascade. Emitted under a distinct type so routing can
    # send it to the rendered contrast strategy.
    "color-contrast": {
        "type": "computed-contrast-insufficient",
        "wcag": "1.4.3",
        "severity": "major",
    },
    # Name, Role, Value (WCAG 4.1.2) — accessible name resolved from the a11y
    # tree. axe emits a distinct rule id per control kind; they all map to the
    # same remediable "missing-accessible-name" type. Native buttons/links plus
    # custom-widget roles (role="button"/"link"), toggles/switches/checkboxes,
    # menu commands, and form inputs/selects without an accessible name.
    "button-name": {
        "type": "missing-accessible-name", "wcag": "4.1.2", "severity": "critical",
    },
    "link-name": {
        "type": "missing-accessible-name", "wcag": "4.1.2", "severity": "critical",
    },
    "aria-command-name": {
        "type": "missing-accessible-name", "wcag": "4.1.2", "severity": "critical",
    },
    "aria-toggle-field-name": {
        "type": "missing-accessible-name", "wcag": "4.1.2", "severity": "critical",
    },
    "aria-input-field-name": {
        "type": "missing-accessible-name", "wcag": "4.1.2", "severity": "critical",
    },
    "select-name": {
        "type": "missing-accessible-name", "wcag": "4.1.2", "severity": "critical",
    },
    # Role/state integrity (WCAG 4.1.2) — an ARIA widget missing a required
    # attribute or a required owned/parent relationship.
    "aria-required-attr": {
        "type": "missing-aria-state", "wcag": "4.1.2", "severity": "major",
    },
    "aria-required-parent": {
        "type": "invalid-aria-structure", "wcag": "4.1.2", "severity": "major",
    },
    "aria-required-children": {
        "type": "invalid-aria-structure", "wcag": "4.1.2", "severity": "major",
    },
    # Duplicate ids (WCAG 4.1.1 in 2.1; parsing) break label[for]/aria-*
    # references — the reference resolves only to the first match. Routed to a
    # deterministic document-wide de-dup that also repairs label associations.
    "duplicate-id-active": {
        "type": "duplicate-id", "wcag": "4.1.1", "severity": "major",
    },
    "duplicate-id-aria": {
        "type": "duplicate-id", "wcag": "4.1.1", "severity": "major",
    },
}


def _issue_from_parts(
    issue_type: str,
    wcag: str,
    severity: str,
    selector: str,
    element_tag: str,
    description: str,
    page_number: int = 0,
    issue_index: int = 0,
    source: str = "axe",
) -> Dict[str, Any]:
    """Build one issue dict in the canonical shape.

    Mirrors the fields ``AccessibilityAuditor._add_issue`` sets, including the
    derived criterion name/level and the ``remediation_status`` lifecycle
    fields, so a rendered issue is indistinguishable in shape from a static one.
    """
    criterion_info = get_criterion_info(wcag)
    return {
        "id": f"rendered-issue-{issue_index + 1}",
        "type": issue_type,
        "wcag_criterion": wcag,
        "criterion_name": criterion_info.get("name", ""),
        "criterion_level": criterion_info.get("level", ""),
        "severity": severity,
        "element": element_tag,
        "description": description,
        "context": {"detected_by": source},
        "location": {"path": selector, "page_number": page_number},
        "remediation_status": "needs_remediation",
        "remediation_source": None,
        "remediation_date": None,
    }


def _tag_from_selector(selector: str) -> str:
    """Best-effort element tag name from a CSS selector (for the ``element`` field)."""
    if not selector:
        return "unknown"
    last = selector.split(">")[-1].strip()
    tag = ""
    for ch in last:
        if ch.isalnum() or ch == "-":
            tag += ch
        else:
            break
    return tag or "unknown"


class AxeAdapter:
    """Convert a :class:`ProbeResult` into canonical issue dicts."""

    def __init__(self, page_number: int = 0) -> None:
        self.page_number = page_number

    def to_issues(self, probe_result: ProbeResult) -> List[Dict[str, Any]]:
        """Return all issues found in one probe pass, in canonical shape."""
        issues: List[Dict[str, Any]] = []

        # Focus-visible findings (WCAG 2.4.7). This is the interactive check axe
        # does not make; the probe measures it directly.
        for finding in probe_result.focus_findings:
            if finding.has_visible_indicator:
                continue
            issues.append(
                _issue_from_parts(
                    issue_type="focus-not-visible",
                    wcag="2.4.7",
                    severity="major",
                    selector=finding.selector,
                    element_tag=_tag_from_selector(finding.selector),
                    description=(
                        f"Interactive element '{finding.selector}' shows no "
                        f"visible focus indicator when focused (WCAG 2.4.7)."
                    ),
                    page_number=self.page_number,
                    issue_index=len(issues),
                    source="focus-probe",
                )
            )

        # Focus-order findings (WCAG 2.4.3): positive tabindex distorts the tab
        # sequence. Detected by the probe's tab-order walk, not axe.
        for finding in getattr(probe_result, "focus_order_findings", []):
            issues.append(
                _issue_from_parts(
                    issue_type="focus-order-broken",
                    wcag="2.4.3",
                    severity="major",
                    selector=finding.selector,
                    element_tag=_tag_from_selector(finding.selector),
                    description=(
                        f"Element '{finding.selector}' has positive "
                        f"tabindex={finding.tabindex}, which overrides DOM order "
                        f"and creates a confusing keyboard focus sequence "
                        f"(WCAG 2.4.3)."
                    ),
                    page_number=self.page_number,
                    issue_index=len(issues),
                    source="focus-order-probe",
                )
            )

        # axe rule violations we own.
        for violation in probe_result.violations:
            mapping = AXE_RULE_MAP.get(violation.rule_id)
            if mapping is None:
                continue
            for node in violation.nodes:
                issues.append(
                    _issue_from_parts(
                        issue_type=mapping["type"],
                        wcag=mapping["wcag"],
                        severity=mapping["severity"],
                        selector=node.target,
                        element_tag=_tag_from_selector(node.target),
                        description=(
                            f"{violation.help} "
                            f"({node.failure_summary or violation.description})"
                        ).strip(),
                        page_number=self.page_number,
                        issue_index=len(issues),
                        source=f"axe:{violation.rule_id}",
                    )
                )

        return issues


def rendered_issue_types() -> set:
    """Set of issue types this adapter can emit (for de-dup / gating)."""
    types = {"focus-not-visible", "focus-order-broken"}
    types.update(m["type"] for m in AXE_RULE_MAP.values())
    return types
