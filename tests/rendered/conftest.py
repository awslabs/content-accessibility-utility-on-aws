# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Fixtures for the rendered / agent test tier.

Two kinds of tests live here:

- **Browser-free** tests exercise the adapter, de-dup, session ledger, and
  steering-hook logic using ``FakeProbe`` — no Chromium required, so they run in
  the default suite.
- **Browser-backed** tests (``@pytest.mark.rendered``) launch real Chromium via
  ``LocalPlaywrightProbe`` and are skipped unless the browser is available.
- **Agent** tests (``@pytest.mark.aws``) additionally call Bedrock.
"""

from typing import Dict, List, Tuple

import pytest

from content_accessibility_utility_on_aws.agent.browser_probe import (
    BrowserProbe,
    ElementInfo,
    FocusFinding,
    ProbeResult,
    RawViolation,
    RawViolationNode,
    VerifyResult,
)

# A page with a button whose focus outline is removed (WCAG 2.4.7 failure) and
# a heading so the page is otherwise reasonable.
FOCUS_FAIL_HTML = """<!doctype html><html lang="en"><head><title>Demo</title>
<style>button{outline:none;border:1px solid #333;background:#fff;color:#111}</style>
</head><body><main><h1>Hi</h1><button id="go">Go</button></main></body></html>"""


class FakeProbe(BrowserProbe):
    """A scripted ``BrowserProbe`` for browser-free tests.

    - ``render_and_probe`` returns a fixed :class:`ProbeResult`.
    - ``verify`` returns pass/fail based on whether the current HTML contains a
      configured marker string, so tests can simulate "the fix worked" by
      applying an edit that adds the marker.
    """

    def __init__(
        self,
        probe_result: ProbeResult,
        verify_marker: str = "data-a11y-focus-visible",
    ) -> None:
        self._result = probe_result
        self._marker = verify_marker
        self.verify_calls: List[Tuple[str, str]] = []

    def render_and_probe(self, html: str) -> ProbeResult:
        return self._result

    def get_element(self, html: str, selector: str) -> ElementInfo:
        return ElementInfo(found=True, selector=selector, tag="button")

    def verify(self, html: str, selector: str, criterion: str) -> VerifyResult:
        self.verify_calls.append((selector, criterion))
        passed = self._marker in html
        return VerifyResult(
            criterion=criterion,
            selector=selector,
            passed=passed,
            detail="marker present" if passed else "marker absent",
        )


@pytest.fixture
def focus_fail_probe_result() -> ProbeResult:
    """A ProbeResult representing one focus-visible failure on button#go."""
    return ProbeResult(
        violations=[],
        focus_findings=[
            FocusFinding(
                selector="button#go",
                html="<button id='go'>Go</button>",
                has_visible_indicator=False,
            )
        ],
    )


@pytest.fixture
def contrast_probe_result() -> ProbeResult:
    """A ProbeResult with an axe color-contrast violation."""
    return ProbeResult(
        violations=[
            RawViolation(
                rule_id="color-contrast",
                impact="serious",
                description="Elements must meet minimum contrast",
                help="Elements must have sufficient color contrast",
                help_url="https://dequeuniversity.com/rules/axe/4.10/color-contrast",
                wcag_tags=["wcag2aa", "wcag143"],
                nodes=[
                    RawViolationNode(
                        target="p.lo",
                        html="<p class='lo'>low</p>",
                        failure_summary="contrast 2.1:1, need 4.5:1",
                    )
                ],
            )
        ],
        focus_findings=[],
    )


def _browser_probe_or_skip():
    """Return a live LocalPlaywrightProbe, or skip the test if unavailable."""
    from content_accessibility_utility_on_aws.agent.browser_probe import (
        BrowserUnavailableError,
        LocalPlaywrightProbe,
    )

    probe = LocalPlaywrightProbe()
    try:
        # Cheap render to confirm the browser actually launches here.
        probe.render_and_probe("<!doctype html><html><body></body></html>")
    except BrowserUnavailableError as e:
        probe.close()
        pytest.skip(f"Headless browser unavailable: {e}")
    return probe


@pytest.fixture
def browser_probe():
    """A real LocalPlaywrightProbe, skipped if Chromium can't launch."""
    probe = _browser_probe_or_skip()
    yield probe
    probe.close()
