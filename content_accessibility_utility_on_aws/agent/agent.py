# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
The browser-backed accessibility agent, built on Strands.

This is the "agent-first" spine from the project plan. A Strands ``Agent`` (a
Bedrock model plus a toolbelt) is given the goal "make this page pass its
failing WCAG checks" and drives the loop itself:

    render_and_probe -> (choose a fix) -> apply_fix -> verify -> repeat -> commit

The model decides *which* fix, in *what* order, and *whether to keep trying*.
Detection and verification are deterministic tools; the model never performs
them itself.

Two things keep the model honest, enforced by a Strands steering hook
(:class:`VerificationHook`) regardless of what the model does:

    1. A resolution can only be committed (``mark_issue_resolved``) when a
       deterministic ``verify`` pass is recorded for that (selector, criterion).
       The hook cancels the commit otherwise.

This module also exposes :func:`run_agent`, which wires a session + tools +
hook + model and runs one page to completion, returning the remediated HTML,
the committed resolutions, and the full tool-call trace (for tests/observability).

When AI is disabled or Strands/Bedrock is unavailable, callers should use
``deterministic_loop.run_deterministic`` instead; ``run_agent`` deliberately
does not silently fall back so the two paths stay distinguishable.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from content_accessibility_utility_on_aws.agent.browser_probe import BrowserProbe
from content_accessibility_utility_on_aws.agent.session import AgentSession
from content_accessibility_utility_on_aws.utils.constants import (
    DEFAULT_MODEL_ID,
    model_supports_temperature,
)
from content_accessibility_utility_on_aws.utils.logging_helper import setup_logger

logger = setup_logger(__name__)

SYSTEM_PROMPT = """\
You are an accessibility remediation agent. Your goal is to make the current \
HTML page pass its failing WCAG success criteria, one issue at a time.

You have these tools:
- render_and_probe(): render the page in a real browser and return the list of \
outstanding accessibility issues (type, wcag_criterion, selector, description).
- get_element(selector): inspect one element's computed style, box, role, and \
accessible name.
- apply_fix(selector, issue_type): apply the remediation for that issue type at \
that selector. This edits the page but does NOT prove the fix worked.
- author_css_rule(selector, declarations): inject a real CSS rule. Use this for \
contrast (1.4.3 / 1.4.11): read the element's computed color and \
background-color with get_element, pick colors meeting the threshold (>= 4.5:1 \
normal text, >= 3:1 large text / UI components), then apply e.g. \
"color:#111 !important; background-color:#fff !important". apply_fix does not fix \
contrast; author_css_rule does.
- set_page_state(script): run a small JS snippet after render to reach a runtime \
state (e.g. "openModal();"), then re-probe in that state. Use this when an issue \
only exists after interaction — a modal hidden until opened, a live region that \
updates on an action. All later probes/verify observe that state; pass "" to \
reset.
- verify(selector, criterion): re-render the page and re-measure whether that \
element now satisfies that WCAG criterion. This is the ONLY source of truth for \
whether a fix worked. Returns passed=true/false and a detail.
- mark_issue_resolved(selector, criterion): record an issue as resolved. You may \
ONLY call this after verify() returned passed=true for the same selector and \
criterion; otherwise it will be rejected.

Process:
1. Call render_and_probe() to see the outstanding issues.
2. For each issue: optionally inspect with get_element, then apply_fix, then \
verify. If verify returns passed=false, reconsider and try a different approach \
before giving up. If it returns passed=true, call mark_issue_resolved.
3. When all issues you can fix are resolved, call render_and_probe() once more to \
confirm, then stop and briefly summarize what you fixed.

Never claim an issue is fixed without a passing verify(). Do not fabricate \
selectors — only use selectors returned by render_and_probe or get_element.
"""


def build_tools(session: AgentSession) -> List[Any]:
    """Create the four probe/DOM tools plus the guarded commit tool.

    Tools are thin wrappers over :class:`AgentSession`; they are defined inside
    this function so each captures the specific session for this run.
    """
    from strands import tool

    @tool
    def render_and_probe() -> str:
        """Render the page in a browser and list outstanding accessibility issues.

        Returns a JSON array of issues, each with: type, wcag_criterion,
        selector, severity, description.
        """
        issues = session.probe_page()
        return AgentSession.issues_to_json(issues)

    @tool
    def get_element(selector: str) -> Dict[str, Any]:
        """Inspect one element's computed style, bounding box, role, and name.

        Args:
            selector: A CSS selector returned by render_and_probe.
        """
        return session.element_info(selector)

    @tool
    def apply_fix(selector: str, issue_type: str) -> str:
        """Apply the remediation for an issue type at a selector (edits the page).

        This does not prove the fix worked; call verify afterward.

        Args:
            selector: The CSS selector of the element to fix.
            issue_type: The issue type to remediate (e.g. 'focus-not-visible').
        """
        return session.apply_fix(selector, issue_type)

    @tool
    def author_css_rule(selector: str, declarations: str) -> str:
        """Inject a real CSS rule into the page: `selector { declarations }`.

        Use this for fixes that a per-element attribute cannot express because
        the failing style comes from a stylesheet that wins the cascade — most
        importantly contrast (1.4.3 / 1.4.11). First read the element's computed
        color and background-color with get_element, choose colors that meet the
        contrast threshold (>= 4.5:1 for normal text, >= 3:1 for large text or UI
        components), then apply them here. Include `!important` in declarations
        when overriding an existing rule. Call verify(selector, '1.4.3') after.

        Args:
            selector: CSS selector the rule targets (reuse one from a probe).
            declarations: CSS declarations, e.g. 'color:#111 !important;
                background-color:#fff !important'.
        """
        return session.author_css_rule(selector, declarations)

    @tool
    def verify(selector: str, criterion: str) -> Dict[str, Any]:
        """Re-render and re-measure whether an element now meets a WCAG criterion.

        This is the only source of truth for whether a fix worked.

        Args:
            selector: The CSS selector of the element to re-check.
            criterion: The WCAG criterion number, e.g. '2.4.7'.
        """
        return session.verify(selector, criterion)

    @tool
    def set_page_state(script: str) -> str:
        """Drive the page into a runtime state, then re-probe in that state.

        Some issues only exist after interaction — a modal that is hidden until
        openModal() runs (so its missing dialog role / label / focus trap is
        invisible on the initial render), or a live region that only updates on
        an action. Provide a small JS snippet to reach that state (e.g.
        "openModal();" or "document.querySelector('.tab:nth-child(2)').click();").
        Every later probe/verify observes that state until you call this again;
        pass an empty string to return to the initial page. Returns the issues
        found in the new state (same shape as render_and_probe).

        Args:
            script: JavaScript to execute after render to reach the state.
        """
        return session.set_page_state(script)

    @tool
    def mark_issue_resolved(selector: str, criterion: str) -> str:
        """Record an issue as resolved. Only valid after a passing verify().

        Args:
            selector: The CSS selector of the resolved element.
            criterion: The WCAG criterion number that now passes.
        """
        return session.commit_resolution(selector, criterion)

    return [
        render_and_probe,
        get_element,
        apply_fix,
        author_css_rule,
        set_page_state,
        verify,
        mark_issue_resolved,
    ]


def build_verification_hook(session: AgentSession):
    """Build the steering hook that enforces verify-before-commit.

    Returns a ``HookProvider`` that cancels any ``mark_issue_resolved`` call
    whose (selector, criterion) has no recorded deterministic verify pass.
    """
    from strands.hooks import BeforeToolCallEvent, HookProvider, HookRegistry

    class VerificationHook(HookProvider):
        """Reject commits that are not backed by a passing verify()."""

        def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
            registry.add_callback(BeforeToolCallEvent, self._before_tool)

        def _before_tool(self, event: BeforeToolCallEvent) -> None:
            tool_use = event.tool_use
            if not tool_use or tool_use.get("name") != "mark_issue_resolved":
                return
            args = tool_use.get("input") or {}
            selector = args.get("selector")
            criterion = args.get("criterion")
            if not session.is_verified(selector, criterion):
                # Cancel with an explanatory message; Strands turns this into a
                # tool error the model sees, so it learns to verify first.
                event.cancel_tool = (
                    f"Refused to mark {selector} ({criterion}) resolved: no "
                    f"passing verify() on record. Call verify() first."
                )
                logger.warning(
                    "Steering hook blocked unverified commit: %s / %s",
                    selector,
                    criterion,
                )

    return VerificationHook()


def run_agent(
    probe: BrowserProbe,
    html: str,
    options: Optional[Dict[str, Any]] = None,
    model_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Run the Strands agent over one page and return the outcome.

    Args:
        probe: A ready browser probe (local or hosted).
        html: The page HTML to remediate.
        options: Remediation options (passed to RemediationManager).
        model_id: Bedrock model id; defaults to the project default.

    Returns:
        dict with ``html`` (remediated), ``resolved`` (committed resolutions),
        ``tool_log`` (full tool-call trace), and ``summary`` (model's final text).
    """
    from strands import Agent
    from strands.models import BedrockModel

    options = options or {}
    session = AgentSession(probe=probe, html=html, options=options)
    tools = build_tools(session)
    hook = build_verification_hook(session)

    resolved_model_id = model_id or options.get("model_id", DEFAULT_MODEL_ID)
    # Some models (e.g. Claude Sonnet 5) reject `temperature`; omit it for those
    # so the agent stays model-agnostic. Deterministic output for models that do
    # accept it still comes from temperature=0.0.
    model_kwargs = {"model_id": resolved_model_id}
    if model_supports_temperature(resolved_model_id):
        model_kwargs["temperature"] = 0.0
    model = BedrockModel(**model_kwargs)
    agent = Agent(
        model=model,
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
        hooks=[hook],
        name="accessibility-remediation-agent",
        description="Renders a page, fixes interactive WCAG issues, verifies each fix.",
    )

    result = agent("Remediate this page's accessibility issues.")
    summary = str(result)

    return {
        "html": session.html,
        "resolved": session.resolved,
        "tool_log": session.tool_log,
        "summary": summary,
    }
