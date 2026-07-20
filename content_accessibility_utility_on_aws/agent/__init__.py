# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Browser-backed accessibility agent.

This package adds a *rendered* accessibility layer on top of the existing
static-HTML audit/remediate pipeline. Where the static pipeline sees only the
source HTML plus inline CSS, this layer renders the page in a real headless
browser and probes the computed styles, the accessibility tree, and interactive
behavior (keyboard/focus). It then closes the loop that the static pipeline
never does: apply a fix, re-render, and *verify* the fix actually worked.

The layer is entirely optional. Nothing here is imported by the core package;
it is only reachable when the caller opts in (``options["rendered"]`` /
``options["agent"]``) and the optional dependencies are installed
(``pip install content-accessibility-utility-on-aws[agent]``).

Key pieces:
    - ``browser_probe`` — the ``BrowserProbe`` interface and a local Playwright
      implementation that renders soup HTML, injects axe-core, and exposes the
      deterministic probes (axe scan, focus-style diff, element inspection).
    - ``axe_adapter`` — maps browser probe output into the canonical issue-dict
      shape the existing auditor/report/remediation pipeline already consumes.
    - ``agent`` — the Strands ``Agent``, its ``@tool`` functions (built by
      ``build_tools``), and the steering hooks that enforce the
      detect-and-verify invariants.
    - ``session`` — the shared per-run state the tools operate on (the page, the
      probe, and the verification ledger).
    - ``pipeline`` — the deployment-agnostic managed-pipeline core (S3 convert →
      audit → agent-remediate → re-audit), invoked by the AgentCore entrypoint.
    - ``deterministic_loop`` — the no-LLM fallback used when ``disable_ai`` is set.
"""

from content_accessibility_utility_on_aws.agent.browser_probe import (
    BrowserProbe,
    LocalPlaywrightProbe,
    AgentCoreBrowserProbe,
    make_browser_probe,
    ProbeResult,
    ElementInfo,
    VerifyResult,
    BrowserUnavailableError,
)

__all__ = [
    "BrowserProbe",
    "LocalPlaywrightProbe",
    "AgentCoreBrowserProbe",
    "make_browser_probe",
    "ProbeResult",
    "ElementInfo",
    "VerifyResult",
    "BrowserUnavailableError",
]
