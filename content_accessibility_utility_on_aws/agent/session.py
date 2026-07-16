# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Agent session: the shared, mutable state the agent's tools operate on.

A Strands ``@tool`` is a plain function, so the four tools need somewhere to
share the page being remediated, the browser probe, the remediation engine, and
— critically — the *verification ledger* that records which (selector,
criterion) pairs a deterministic ``verify`` re-probe has actually confirmed as
fixed.

The ledger is the enforcement point for the plan's core invariant:

    "Verification is always the re-probe, never the model. A fix counts as done
     only when a probe re-measurement passes."

Only :meth:`AgentSession.verify` may write a *pass* into the ledger, and it does
so from the deterministic probe result — never from anything the model says.
The commit tool (``mark_issue_resolved``) then reads the ledger under a steering
hook that rejects any commit lacking a recorded pass.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

from bs4 import BeautifulSoup

from content_accessibility_utility_on_aws.agent.browser_probe import BrowserProbe
from content_accessibility_utility_on_aws.agent.rendered_auditor import RenderedAuditor
from content_accessibility_utility_on_aws.remediate.remediation_manager import (
    RemediationManager,
)
from content_accessibility_utility_on_aws.utils.logging_helper import setup_logger

logger = setup_logger(__name__)


@dataclass
class AgentSession:
    """Mutable state shared across an agent run over a single page."""

    probe: BrowserProbe
    html: str
    options: Dict[str, Any] = field(default_factory=dict)

    # Verification ledger: (selector, criterion) -> passed. Written ONLY by
    # verify(), and only from the deterministic probe result.
    verified: Dict[Tuple[str, str], bool] = field(default_factory=dict)
    # Committed resolutions the agent claims are done (guarded by the hook).
    resolved: List[Dict[str, str]] = field(default_factory=list)
    # A running log of tool calls for observability / tests.
    tool_log: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._auditor = RenderedAuditor(self.probe)
        self._manager_cache = None

    def _manager(self) -> RemediationManager:
        """Return a reused RemediationManager (built lazily on first fix)."""
        if self._manager_cache is None:
            self._manager_cache = RemediationManager(
                BeautifulSoup("", "html.parser"), self.options
            )
        return self._manager_cache

    # -- tool-backing operations ------------------------------------------

    def probe_page(self) -> List[Dict[str, Any]]:
        """Render the current HTML and return the outstanding rendered issues."""
        issues = self._auditor.audit_html(self.html)
        self._record("render_and_probe", {}, {"issue_count": len(issues)})
        return issues

    def element_info(self, selector: str) -> Dict[str, Any]:
        """Return computed info for one element as a plain dict."""
        info = self.probe.get_element(self.html, selector)
        result = {
            "found": info.found,
            "tag": info.tag,
            "computed_style": info.computed_style,
            "bounding_box": info.bounding_box,
            "accessible_name": info.accessible_name,
            "role": info.role,
            "outer_html": info.outer_html,
        }
        self._record("get_element", {"selector": selector}, {"found": info.found})
        return result

    def apply_fix(self, selector: str, issue_type: str) -> str:
        """Apply the mapped remediation strategy for ``issue_type`` at ``selector``.

        Mutates ``self.html`` in place (via the shared BeautifulSoup tree and
        the existing ``RemediationManager`` routing). Returns the strategy's
        message, or an error string. Applying a fix does NOT mark anything
        verified — the agent must call :meth:`verify` afterward.
        """
        # The current HTML string is the source of truth (verify re-parses it
        # too), so a fresh soup is needed each call, but the RemediationManager —
        # which builds a ~40-entry strategy registry and may construct a Bedrock
        # client — is created once and reused, only pointing it at the new soup.
        soup = BeautifulSoup(self.html, "html.parser")
        manager = self._manager()
        manager.soup = soup
        issue = {
            "id": "agent-fix",
            "type": issue_type,
            "location": {"path": selector},
            "element": "",
        }
        try:
            message = manager.remediate_issue(issue)
        except Exception as e:  # pragma: no cover - defensive
            logger.error("apply_fix failed: %s", e)
            message = None
        if message is None:
            self._record(
                "apply_fix",
                {"selector": selector, "issue_type": issue_type},
                {"applied": False},
            )
            return f"No fix applied for '{issue_type}' at '{selector}'."
        # Commit the mutated DOM back as the new current state.
        self.html = str(soup)
        self._record(
            "apply_fix",
            {"selector": selector, "issue_type": issue_type},
            {"applied": True, "message": message},
        )
        return message

    def verify(self, selector: str, criterion: str) -> Dict[str, Any]:
        """Re-render and re-probe one node/criterion; record the passing result.

        This is the ONLY writer of a passing entry in the verification ledger,
        and the value comes straight from the deterministic probe.
        """
        result = self.probe.verify(self.html, selector, criterion)
        self.verified[(selector, criterion)] = bool(result.passed)
        self._record(
            "verify",
            {"selector": selector, "criterion": criterion},
            {"passed": result.passed, "detail": result.detail},
        )
        return {
            "selector": selector,
            "criterion": criterion,
            "passed": result.passed,
            "detail": result.detail,
        }

    def is_verified(self, selector: str, criterion: str) -> bool:
        """True only if a deterministic verify pass is recorded for this pair."""
        return self.verified.get((selector, criterion), False)

    def commit_resolution(self, selector: str, criterion: str) -> str:
        """Record a resolution. Assumes the steering hook has already gated it."""
        self.resolved.append({"selector": selector, "criterion": criterion})
        self._record(
            "mark_issue_resolved",
            {"selector": selector, "criterion": criterion},
            {"committed": True},
        )
        return f"Issue at '{selector}' ({criterion}) recorded as resolved."

    # -- helpers ----------------------------------------------------------

    def _record(self, tool: str, args: Dict[str, Any], result: Dict[str, Any]) -> None:
        self.tool_log.append({"tool": tool, "args": args, "result": result})

    @staticmethod
    def issues_to_json(issues: List[Dict[str, Any]]) -> str:
        """Compact JSON the model can read: type, criterion, selector, description."""
        slim = [
            {
                "type": i["type"],
                "wcag_criterion": i["wcag_criterion"],
                "selector": i["location"].get("path"),
                "severity": i.get("severity"),
                "description": i.get("description", ""),
            }
            for i in issues
        ]
        return json.dumps(slim)
