# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Tests for the runtime page-state capability (#3): AgentSession.set_page_state
threads a JS snippet into the probe so runtime-only issues (a modal hidden until
opened, a live region) become observable. Browser-free via a fake probe.
"""

import json

from content_accessibility_utility_on_aws.agent.session import AgentSession


class _FakeProbe:
    """Records the state script and returns different findings per state."""

    def __init__(self):
        self.state = None

    def set_state_script(self, script):
        self.state = script

    # RenderedAuditor calls render_and_probe; the session's probe_page goes
    # through RenderedAuditor, so we stub that path via a minimal ProbeResult.
    def render_and_probe(self, html):
        from content_accessibility_utility_on_aws.agent.browser_probe import (
            ProbeResult,
            RawViolation,
            RawViolationNode,
        )
        # Pristine: no violations. With a modal opened: one button-name violation.
        if self.state and "openModal" in self.state:
            return ProbeResult(
                violations=[
                    RawViolation(
                        rule_id="button-name",
                        impact="critical",
                        description="Buttons must have discernible text",
                        help="Buttons must have discernible text",
                        help_url="",
                        wcag_tags=["wcag412"],
                        nodes=[RawViolationNode(target="#m span", html="<span>")],
                    )
                ]
            )
        return ProbeResult()


def _session():
    return AgentSession(probe=_FakeProbe(), html="<html><body></body></html>")


def test_set_page_state_reveals_runtime_issue():
    s = _session()
    before = json.loads(AgentSession.issues_to_json(s.probe_page()))
    assert before == []  # nothing visible pristine

    exposed = json.loads(s.set_page_state("openModal();"))
    assert len(exposed) == 1
    assert exposed[0]["type"] == "missing-accessible-name"
    assert s.probe.state == "openModal();"  # threaded into the probe


def test_set_page_state_reset_clears_script():
    s = _session()
    s.set_page_state("openModal();")
    s.set_page_state("")  # reset
    assert s.probe.state is None


def test_set_page_state_rejects_markup():
    s = _session()
    msg = s.set_page_state("</script><script>alert(1)")
    assert "Rejected" in msg
    assert s.probe.state is None  # never applied


def test_set_page_state_rejects_document_write():
    s = _session()
    msg = s.set_page_state("document.write('x')")
    assert "Rejected" in msg


def test_set_page_state_recorded_in_tool_log():
    s = _session()
    s.set_page_state("openModal();")
    assert any(e["tool"] == "set_page_state" for e in s.tool_log)
