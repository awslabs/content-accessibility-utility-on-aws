# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Browser-free tests for the agent session ledger and the steering hook.

These pin the plan's central invariant — a resolution can only be committed
when a deterministic verify() pass is recorded — without needing Chromium or
Bedrock. They use ``FakeProbe`` and drive the hook by constructing the same
``BeforeToolCallEvent`` Strands would.
"""

import pytest

from content_accessibility_utility_on_aws.agent.session import AgentSession
from tests.rendered.conftest import FOCUS_FAIL_HTML, FakeProbe


def test_verify_is_only_writer_of_ledger(focus_fail_probe_result):
    probe = FakeProbe(focus_fail_probe_result)
    session = AgentSession(probe=probe, html=FOCUS_FAIL_HTML)

    # Nothing verified yet.
    assert session.is_verified("button#go", "2.4.7") is False

    # Apply the real focus fix -> the marker appears in the HTML, so FakeProbe's
    # verify() returns passed=True, and the ledger records it.
    msg = session.apply_fix("button#go", "focus-not-visible")
    assert "focus" in msg.lower()
    result = session.verify("button#go", "2.4.7")
    assert result["passed"] is True
    assert session.is_verified("button#go", "2.4.7") is True


def test_verify_records_failure_when_fix_not_applied(focus_fail_probe_result):
    probe = FakeProbe(focus_fail_probe_result)
    session = AgentSession(probe=probe, html=FOCUS_FAIL_HTML)
    # Verify WITHOUT applying the fix -> marker absent -> not verified.
    result = session.verify("button#go", "2.4.7")
    assert result["passed"] is False
    assert session.is_verified("button#go", "2.4.7") is False


def _fire_before_tool(hook, name, tool_input):
    """Build and dispatch a BeforeToolCallEvent through the hook; return it."""
    from strands.hooks import BeforeToolCallEvent, HookRegistry

    registry = HookRegistry()
    hook.register_hooks(registry)
    event = BeforeToolCallEvent(
        agent=None,
        selected_tool=None,
        tool_use={"name": name, "toolUseId": "t", "input": tool_input},
        invocation_state={},
    )
    registry.invoke_callbacks(event)
    return event


def test_steering_hook_blocks_unverified_commit(focus_fail_probe_result):
    pytest.importorskip("strands")  # hook is built via agent.py, which imports strands
    from content_accessibility_utility_on_aws.agent.agent import (
        build_verification_hook,
    )

    probe = FakeProbe(focus_fail_probe_result)
    session = AgentSession(probe=probe, html=FOCUS_FAIL_HTML)
    hook = build_verification_hook(session)

    # No verify pass on record -> commit must be cancelled with a message.
    event = _fire_before_tool(
        hook, "mark_issue_resolved", {"selector": "button#go", "criterion": "2.4.7"}
    )
    assert event.cancel_tool  # truthy string message
    assert "verify" in str(event.cancel_tool).lower()


def test_steering_hook_allows_verified_commit(focus_fail_probe_result):
    pytest.importorskip("strands")
    from content_accessibility_utility_on_aws.agent.agent import (
        build_verification_hook,
    )

    probe = FakeProbe(focus_fail_probe_result)
    session = AgentSession(probe=probe, html=FOCUS_FAIL_HTML)
    session.verified[("button#go", "2.4.7")] = True  # simulate a recorded pass
    hook = build_verification_hook(session)

    event = _fire_before_tool(
        hook, "mark_issue_resolved", {"selector": "button#go", "criterion": "2.4.7"}
    )
    assert event.cancel_tool is False


def test_steering_hook_ignores_other_tools(focus_fail_probe_result):
    pytest.importorskip("strands")
    from content_accessibility_utility_on_aws.agent.agent import (
        build_verification_hook,
    )

    probe = FakeProbe(focus_fail_probe_result)
    session = AgentSession(probe=probe, html=FOCUS_FAIL_HTML)
    hook = build_verification_hook(session)

    event = _fire_before_tool(hook, "apply_fix", {"selector": "button#go"})
    assert event.cancel_tool is False


def test_deterministic_loop_with_fake_probe(focus_fail_probe_result):
    """The no-LLM loop resolves the focus issue and only commits after verify."""
    from content_accessibility_utility_on_aws.agent.deterministic_loop import (
        run_deterministic,
    )

    probe = FakeProbe(focus_fail_probe_result)
    out = run_deterministic(probe, FOCUS_FAIL_HTML)
    assert out["resolved"] == [{"selector": "button#go", "criterion": "2.4.7"}]
    assert "data-a11y-focus-visible" in out["html"]
    # The trace shows verify ran before the commit.
    tools = [e["tool"] for e in out["tool_log"]]
    assert tools.index("verify") < tools.index("mark_issue_resolved")
