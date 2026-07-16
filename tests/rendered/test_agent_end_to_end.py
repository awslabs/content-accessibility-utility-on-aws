# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Agent end-to-end test (requires Chromium AND Bedrock).

This is the plan's MVP acceptance test: the *Strands agent* — not a hardcoded
loop — drives render_and_probe -> apply_fix -> verify -> mark_issue_resolved and
closes the focus-visible loop. It asserts against the agent's tool-call trace so
we prove the agent did the work.

Run with: ``pytest -m "rendered and aws"`` with AWS credentials configured.
"""

import pytest

from tests.rendered.conftest import FOCUS_FAIL_HTML

pytestmark = [pytest.mark.rendered, pytest.mark.aws]

# A cheap, capable Converse model for the test; override via the usual env if needed.
_TEST_MODEL = "us.anthropic.claude-haiku-4-5-20251001-v1:0"


def test_agent_closes_focus_visible_loop(browser_probe):
    from content_accessibility_utility_on_aws.agent.agent import run_agent

    out = run_agent(browser_probe, FOCUS_FAIL_HTML, model_id=_TEST_MODEL)

    tools_called = [e["tool"] for e in out["tool_log"]]
    # The agent must have gone through the full sense-act-verify-commit cycle.
    assert "render_and_probe" in tools_called
    assert "apply_fix" in tools_called
    assert "verify" in tools_called
    assert "mark_issue_resolved" in tools_called

    # Ordering: verify precedes the (allowed) commit.
    assert tools_called.index("verify") < tools_called.index("mark_issue_resolved")

    # The committed resolution and the resulting HTML both reflect the fix.
    assert {"selector": "button#go", "criterion": "2.4.7"} in out["resolved"]
    assert "data-a11y-focus-visible" in out["html"]

    # Verification that got committed was actually a passing probe result.
    verify_events = [e for e in out["tool_log"] if e["tool"] == "verify"]
    assert any(e["result"]["passed"] for e in verify_events)
