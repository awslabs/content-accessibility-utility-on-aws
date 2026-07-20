# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Deterministic (no-LLM) fallback for the rendered remediation loop.

This is the ``disable_ai`` path. It runs the same sense-act-verify loop as the
Strands agent, but with a fixed policy instead of a model controller: for every
outstanding rendered issue that has a mapped remediation strategy, apply the
fix, then verify. It only records a resolution when the deterministic verify
re-probe passes — the exact same invariant the agent's steering hook enforces.

It uses the same :class:`AgentSession`, so the code paths for applying fixes and
verifying are identical to the agent's; only "who decides what to do" differs.
Interactive issues that need semantic authoring (and thus a model) are left
unresolved and reported, mirroring how the tool already handles model-off cases.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from content_accessibility_utility_on_aws.agent.browser_probe import BrowserProbe
from content_accessibility_utility_on_aws.agent.session import AgentSession
from content_accessibility_utility_on_aws.utils.logging_helper import setup_logger

logger = setup_logger(__name__)


def run_deterministic(
    probe: BrowserProbe,
    html: str,
    options: Optional[Dict[str, Any]] = None,
    max_rounds: int = 3,
) -> Dict[str, Any]:
    """Run the fixed-policy rendered remediation loop over one page.

    Args:
        probe: A ready browser probe.
        html: The page HTML to remediate.
        options: Remediation options (``disable_ai`` is forced on here).
        max_rounds: Safety bound on probe/fix/verify rounds.

    Returns:
        dict with ``html`` (remediated), ``resolved``, and ``tool_log`` — the
        same shape ``run_agent`` returns, so callers are interchangeable.
    """
    options = dict(options or {})
    options["disable_ai"] = True
    session = AgentSession(probe=probe, html=html, options=options)

    for round_num in range(max_rounds):
        issues = session.probe_page()
        actionable = [i for i in issues if not _already_resolved(session, i)]
        if not actionable:
            logger.debug("Deterministic loop converged after %d round(s)", round_num)
            break

        progressed = False
        for issue in actionable:
            selector = issue["location"].get("path")
            criterion = issue["wcag_criterion"]
            issue_type = issue["type"]

            message = session.apply_fix(selector, issue_type)
            if message.startswith("No fix applied"):
                # No deterministic strategy for this type (e.g. needs authoring).
                continue

            result = session.verify(selector, criterion)
            if result["passed"]:
                session.commit_resolution(selector, criterion)
                progressed = True
            else:
                logger.debug(
                    "Deterministic fix did not verify: %s (%s)", selector, criterion
                )

        if not progressed:
            # Nothing else we can deterministically fix; stop to avoid spinning.
            break

    return {
        "html": session.html,
        "resolved": session.resolved,
        "tool_log": session.tool_log,
        "summary": (
            f"Deterministic loop resolved {len(session.resolved)} issue(s)."
        ),
    }


def _already_resolved(session: AgentSession, issue: Dict[str, Any]) -> bool:
    selector = issue["location"].get("path")
    criterion = issue["wcag_criterion"]
    return {"selector": selector, "criterion": criterion} in session.resolved
