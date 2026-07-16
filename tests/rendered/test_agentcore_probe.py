# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Browser-free tests for the AgentCore browser probe and the probe factory.

These do not start a real AgentCore session or a browser; they verify backend
selection, region resolution, and that ``_connect_browser`` drives the AgentCore
SDK + Playwright the way the hosted path expects (both faked). This keeps the
hosted path covered without AWS access.
"""

import sys
import types

import pytest

from content_accessibility_utility_on_aws.agent.browser_probe import (
    AgentCoreBrowserProbe,
    BrowserUnavailableError,
    LocalPlaywrightProbe,
    make_browser_probe,
)


def test_factory_defaults_to_local():
    probe = make_browser_probe({})
    try:
        assert isinstance(probe, LocalPlaywrightProbe)
    finally:
        probe.close()


def test_factory_selects_agentcore_by_option():
    probe = make_browser_probe(
        {"browser_backend": "agentcore", "agentcore_region": "us-west-2"}
    )
    try:
        assert isinstance(probe, AgentCoreBrowserProbe)
        assert probe._region == "us-west-2"
    finally:
        probe.close()


def test_factory_selects_agentcore_by_env(monkeypatch):
    monkeypatch.setenv("A11Y_BROWSER_BACKEND", "agentcore")
    probe = make_browser_probe({})
    try:
        assert isinstance(probe, AgentCoreBrowserProbe)
    finally:
        probe.close()


def test_agentcore_requires_region(monkeypatch):
    monkeypatch.delenv("AWS_REGION", raising=False)
    monkeypatch.delenv("AWS_DEFAULT_REGION", raising=False)
    probe = AgentCoreBrowserProbe(region=None)
    with pytest.raises(BrowserUnavailableError, match="region"):
        # _connect_browser is what validates region; call it directly with a
        # dummy playwright since it should fail before using it.
        probe._connect_browser(playwright=object())
    probe.close()


class _FakeBrowserClient:
    """Stand-in for bedrock_agentcore BrowserClient — records calls."""

    last = None

    def __init__(self, region=None):
        self.region = region
        self.started = False
        self.stopped = False
        self.start_kwargs = None
        _FakeBrowserClient.last = self

    def start(self, **kwargs):
        self.started = True
        self.start_kwargs = kwargs
        return "session-id"

    def generate_ws_headers(self):
        return "wss://agentcore.example/cdp", {"Authorization": "SigV4 ..."}

    def stop(self):
        self.stopped = True
        return True


class _FakePlaywright:
    """Fake Playwright whose connect_over_cdp records how it was called."""

    def __init__(self):
        self.chromium = self
        self.connected = None

    def connect_over_cdp(self, ws_url, headers=None):
        self.connected = {"ws_url": ws_url, "headers": headers}
        return object()  # a stand-in Browser handle


def _install_fake_agentcore(monkeypatch):
    """Install a fake bedrock_agentcore.tools.browser_client module."""
    mod = types.ModuleType("bedrock_agentcore.tools.browser_client")
    mod.BrowserClient = _FakeBrowserClient
    pkg = types.ModuleType("bedrock_agentcore")
    tools = types.ModuleType("bedrock_agentcore.tools")
    monkeypatch.setitem(sys.modules, "bedrock_agentcore", pkg)
    monkeypatch.setitem(sys.modules, "bedrock_agentcore.tools", tools)
    monkeypatch.setitem(sys.modules, "bedrock_agentcore.tools.browser_client", mod)


def test_agentcore_connect_starts_session_and_connects_cdp(monkeypatch):
    _install_fake_agentcore(monkeypatch)
    probe = AgentCoreBrowserProbe(region="us-west-2", identifier="aws.browser.v1")
    fake_pw = _FakePlaywright()

    browser = probe._connect_browser(fake_pw)

    client = _FakeBrowserClient.last
    assert client.region == "us-west-2"
    assert client.started is True
    # identifier and session timeout are forwarded to start().
    assert client.start_kwargs["identifier"] == "aws.browser.v1"
    assert "session_timeout_seconds" in client.start_kwargs
    # Playwright connected to the CDP endpoint with the signed headers.
    assert fake_pw.connected["ws_url"].startswith("wss://")
    assert "Authorization" in fake_pw.connected["headers"]
    assert browser is not None

    # Teardown stops the managed session so it does not keep billing.
    probe._teardown()
    assert client.stopped is True


def test_agentcore_missing_sdk_raises_browser_unavailable(monkeypatch):
    # Ensure importing the SDK fails.
    monkeypatch.setitem(sys.modules, "bedrock_agentcore.tools.browser_client", None)
    probe = AgentCoreBrowserProbe(region="us-west-2")
    with pytest.raises(BrowserUnavailableError, match="AgentCore SDK"):
        probe._connect_browser(playwright=object())
    probe.close()


class _StartThenFailClient:
    """BrowserClient that starts a (billable) session, then fails to hand off CDP."""

    started = 0
    stopped = 0

    def __init__(self, region=None):
        self.region = region

    def start(self, **kwargs):
        _StartThenFailClient.started += 1

    def generate_ws_headers(self):
        raise RuntimeError("CDP handshake failed after session start")

    def stop(self):
        _StartThenFailClient.stopped += 1


def test_partial_connect_failure_does_not_leak_session(monkeypatch):
    """A start()-then-throw connect must stop the session, even across retries.

    Regression: the probe is reused across pages and audit_html swallows
    BrowserUnavailableError, so without cleanup on failure each retry would
    orphan a billable AgentCore session.
    """
    _StartThenFailClient.started = 0
    _StartThenFailClient.stopped = 0

    mod = types.ModuleType("bedrock_agentcore.tools.browser_client")
    mod.BrowserClient = _StartThenFailClient
    monkeypatch.setitem(sys.modules, "bedrock_agentcore", types.ModuleType("bedrock_agentcore"))
    monkeypatch.setitem(sys.modules, "bedrock_agentcore.tools", types.ModuleType("bedrock_agentcore.tools"))
    monkeypatch.setitem(sys.modules, "bedrock_agentcore.tools.browser_client", mod)

    # Fake Playwright so _ensure_browser reaches _connect_browser without a real browser.
    import playwright.sync_api as pw_api

    class _FakePW:
        def __init__(self):
            self.chromium = self

        def stop(self):
            pass

    class _FakeCtx:
        def start(self):
            return _FakePW()

    monkeypatch.setattr(pw_api, "sync_playwright", lambda: _FakeCtx())

    probe = AgentCoreBrowserProbe(region="us-west-2")
    # Two "pages" both hit the partial-connect failure.
    for _ in range(2):
        with pytest.raises(BrowserUnavailableError):
            probe.render_and_probe("<html></html>")
    probe.close()

    # Every started session was stopped — no leak, no matter how many retries.
    assert _StartThenFailClient.started == _StartThenFailClient.stopped
    assert _StartThenFailClient.started >= 2
