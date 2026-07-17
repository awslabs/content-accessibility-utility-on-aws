# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Browser probe: render HTML and measure what static analysis cannot.

The static audit pipeline parses HTML with BeautifulSoup and reads inline CSS.
It never renders, lays out, or executes the page, so it cannot see computed
styles (contrast from stylesheets/classes), rendered geometry, the accessibility
tree, or interactive behavior such as focus indicators.

``BrowserProbe`` is the seam that fixes this. It defines a small set of
deterministic operations backed by a real browser:

    - ``render_and_probe`` — render the current HTML, run axe-core, run the
      focus-visible probe, and return the raw findings.
    - ``get_element`` — return computed styles / box / a11y info for one node.
    - ``verify`` — re-render and re-check a *single* node against a *single*
      criterion, returning a measured pass/fail. This is what closes the loop.

Two implementations are intended:
    - ``LocalPlaywrightProbe`` (here) — a local headless Chromium via Playwright,
      behind the optional ``[rendered]`` dependency extra.
    - an AgentCore Browser Tool implementation for the hosted path (see the
      project plan); both satisfy this same interface so nothing above the probe
      changes between deployments.

Detection and verification live here and are always deterministic. The agent
(the LLM) never performs detection or verification itself — it only calls these
probes and proposes edits between them.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from content_accessibility_utility_on_aws.utils.logging_helper import setup_logger

logger = setup_logger(__name__)

# axe-core is vendored (pinned) so rendered audits are reproducible and do not
# depend on network access at runtime. See agent/vendor/README.md.
_AXE_JS_PATH = os.path.join(os.path.dirname(__file__), "vendor", "axe.min.js")

# Interactive elements that must show a visible focus indicator (WCAG 2.4.7).
FOCUSABLE_SELECTOR = (
    'a[href], button, input:not([type="hidden"]), select, textarea, '
    '[tabindex]:not([tabindex="-1"]), [role="button"], [role="link"]'
)


class BrowserUnavailableError(RuntimeError):
    """Raised when a browser backend cannot be started.

    Callers should treat this as "the rendered layer is unavailable" and fall
    back to the static pipeline rather than failing the whole run.
    """


@dataclass
class RawViolationNode:
    """One node flagged by axe within a single rule violation."""

    target: str  # CSS selector axe emits for the node (maps to location.path)
    html: str
    failure_summary: str = ""


@dataclass
class RawViolation:
    """A single axe rule violation (may span several nodes)."""

    rule_id: str
    impact: Optional[str]
    description: str
    help: str
    help_url: str
    wcag_tags: List[str] = field(default_factory=list)
    nodes: List[RawViolationNode] = field(default_factory=list)


@dataclass
class FocusFinding:
    """Result of the focus-visible probe for one interactive element."""

    selector: str
    html: str
    # True when focusing the element produces no perceptible style change
    # (no outline/box-shadow/border/background difference) — a 2.4.7 failure.
    has_visible_indicator: bool = True
    base_style: Dict[str, str] = field(default_factory=dict)
    focus_style: Dict[str, str] = field(default_factory=dict)


@dataclass
class FocusOrderFinding:
    """An element whose positive ``tabindex`` distorts focus order (WCAG 2.4.3)."""

    selector: str
    html: str
    tabindex: int


@dataclass
class ProbeResult:
    """Everything one render pass measured."""

    violations: List[RawViolation] = field(default_factory=list)
    focus_findings: List[FocusFinding] = field(default_factory=list)
    focus_order_findings: List[FocusOrderFinding] = field(default_factory=list)


@dataclass
class ElementInfo:
    """Computed information for a single element, for the agent to reason over."""

    found: bool
    selector: str
    tag: Optional[str] = None
    outer_html: Optional[str] = None
    computed_style: Dict[str, str] = field(default_factory=dict)
    bounding_box: Dict[str, float] = field(default_factory=dict)
    accessible_name: Optional[str] = None
    role: Optional[str] = None


@dataclass
class VerifyResult:
    """The measured outcome of re-checking one node against one criterion.

    ``passed`` is the single source of truth for whether a fix "worked". The
    agent is never allowed to set this; only a probe re-measurement can.
    """

    criterion: str
    selector: str
    passed: bool
    measured: Dict[str, Any] = field(default_factory=dict)
    detail: str = ""


class BrowserProbe(ABC):
    """Deterministic, render-backed accessibility probe.

    Implementations render the given HTML and answer three questions: what is
    wrong (``render_and_probe``), what does this node look like when rendered
    (``get_element``), and does this node now satisfy this criterion
    (``verify``).
    """

    @abstractmethod
    def render_and_probe(self, html: str) -> ProbeResult:
        """Render ``html`` and return all findings from this pass."""

    @abstractmethod
    def get_element(self, html: str, selector: str) -> ElementInfo:
        """Render ``html`` and return computed info for ``selector``."""

    @abstractmethod
    def verify(self, html: str, selector: str, criterion: str) -> VerifyResult:
        """Render ``html`` and re-check ``selector`` against ``criterion``."""

    # Optional lifecycle hooks; no-ops by default so callers can always use a
    # ``with probe:`` block regardless of implementation.
    def __enter__(self) -> "BrowserProbe":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def set_state_script(self, script: Optional[str]) -> None:  # pragma: no cover
        """Drive the page into a runtime state before probing (default no-op).

        Implementations backed by a real browser run ``script`` after each
        render (before axe/focus/verify) so runtime-only issues — a modal that
        only exists once opened, a live region that only updates on interaction —
        become observable. Probes without a JS runtime ignore it.
        """

    def close(self) -> None:  # pragma: no cover - trivial
        """Release any backend resources. Safe to call more than once."""


# ---------------------------------------------------------------------------
# Local Playwright implementation
# ---------------------------------------------------------------------------

# JavaScript for the focus-visible probe. For each focusable element it records
# the computed style, focuses it, records the style again, and reports whether
# any of the properties a sighted keyboard user relies on to see focus changed.
# Kept as browser-side JS (rather than reasoning in Python) because only the
# rendering engine knows the true computed cascade and :focus/:focus-visible
# resolution.
_FOCUS_PROBE_JS = r"""
(selector) => {
  const props = ['outline-style', 'outline-width', 'outline-color',
                 'box-shadow', 'border-top-width', 'border-top-color',
                 'border-top-style', 'background-color'];
  const snapshot = (el) => {
    const cs = getComputedStyle(el);
    const out = {};
    for (const p of props) out[p] = cs.getPropertyValue(p);
    return out;
  };
  const cssPath = (el) => {
    if (el.id) return el.tagName.toLowerCase() + '#' + CSS.escape(el.id);
    const parts = [];
    while (el && el.nodeType === 1 && el.tagName.toLowerCase() !== 'html') {
      let seg = el.tagName.toLowerCase();
      const parent = el.parentNode;
      if (parent) {
        const sameTag = Array.from(parent.children).filter(
          c => c.tagName === el.tagName);
        if (sameTag.length > 1) {
          seg += ':nth-of-type(' + (sameTag.indexOf(el) + 1) + ')';
        }
      }
      parts.unshift(seg);
      el = el.parentNode;
    }
    return parts.join(' > ');
  };
  const results = [];
  for (const el of document.querySelectorAll(selector)) {
    const base = snapshot(el);
    el.focus();
    const focused = snapshot(el);
    // A visible indicator exists if focusing changed any tracked property, or
    // if there is already a non-'none' outline while focused.
    let changed = false;
    for (const p of props) { if (base[p] !== focused[p]) { changed = true; break; } }
    const hasOutline = focused['outline-style'] !== 'none' &&
                       parseFloat(focused['outline-width']) > 0;
    el.blur();
    results.push({
      selector: cssPath(el),
      html: el.outerHTML.slice(0, 400),
      has_visible_indicator: changed || hasOutline,
      base_style: base,
      focus_style: focused,
    });
  }
  return results;
}
"""


# Positive tabindex (> 0) forces an element to the front of the tab sequence,
# ahead of DOM order — a common, deterministic WCAG 2.4.3 (Focus Order) defect
# that produces a confusing keyboard sequence. This reports each such element
# with the same cssPath selector convention as the focus probe.
_FOCUS_ORDER_PROBE_JS = r"""
() => {
  const cssPath = (el) => {
    if (el.id) return el.tagName.toLowerCase() + '#' + CSS.escape(el.id);
    const parts = [];
    while (el && el.nodeType === 1 && el.tagName.toLowerCase() !== 'html') {
      let seg = el.tagName.toLowerCase();
      const parent = el.parentNode;
      if (parent) {
        const sameTag = Array.from(parent.children).filter(
          c => c.tagName === el.tagName);
        if (sameTag.length > 1) {
          seg += ':nth-of-type(' + (sameTag.indexOf(el) + 1) + ')';
        }
      }
      parts.unshift(seg);
      el = el.parentNode;
    }
    return parts.join(' > ');
  };
  const results = [];
  for (const el of document.querySelectorAll('[tabindex]')) {
    const ti = parseInt(el.getAttribute('tabindex'), 10);
    if (Number.isFinite(ti) && ti > 0) {
      results.push({selector: cssPath(el), html: el.outerHTML.slice(0, 300), tabindex: ti});
    }
  }
  return results;
}
"""


class _PlaywrightProbeBase(BrowserProbe):
    """Shared Playwright-driven probe logic, independent of *where* the browser is.

    Once a Playwright ``Browser`` handle exists, the render/axe/focus/verify
    logic is identical whether the browser is a local Chromium or a managed
    remote one (e.g. AgentCore Browser Tool over CDP). Subclasses implement only
    :meth:`_connect_browser`, which returns that handle; everything else — the
    axe injection, focus probe, contrast verify, page lifecycle, and the
    event-loop isolation below — lives here so the two deployments cannot drift.

    One browser is created per instance and reused across renders (each render
    uses a fresh page) so repeated probe/verify cycles stay cheap. Determinism
    guards: a fixed viewport, animations disabled, and the pinned vendored
    axe-core build.

    **Event-loop isolation.** Playwright's *sync* API refuses to run inside a
    thread that has a running asyncio event loop. The Strands agent drives its
    tools from inside such a loop (and so do Jupyter/async callers), so every
    browser operation is dispatched onto a dedicated single worker thread that
    never runs a loop. The browser is created and used entirely on that thread.
    """

    def __init__(self, viewport: Optional[Dict[str, int]] = None) -> None:
        self._viewport = viewport or {"width": 1280, "height": 1024}
        self._playwright = None
        self._browser = None
        self._axe_js = self._load_axe()
        # Optional JS run after each render to drive the page into a runtime
        # state before probing (e.g. open a modal). Set via set_state_script so
        # render/get_element/verify all observe the same state. None = pristine.
        self._setup_script: Optional[str] = None
        # All Playwright calls run here so they never see an asyncio loop.
        from concurrent.futures import ThreadPoolExecutor

        self._executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="a11y-browser"
        )

    def _submit(self, fn, *args):
        """Run ``fn`` on the dedicated browser thread and wait for the result."""
        return self._executor.submit(fn, *args).result()

    @staticmethod
    def _load_axe() -> str:
        try:
            with open(_AXE_JS_PATH, "r", encoding="utf-8") as f:
                return f.read()
        except OSError as e:  # pragma: no cover - only if vendoring is broken
            raise BrowserUnavailableError(
                f"Vendored axe-core not found at {_AXE_JS_PATH}: {e}"
            ) from e

    def _connect_browser(self, playwright):
        """Return a Playwright ``Browser`` handle. Implemented by subclasses."""
        raise NotImplementedError

    def _ensure_browser(self):
        if self._browser is not None:
            return
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as e:
            raise BrowserUnavailableError(
                "Playwright is not installed. Install the optional dependency "
                "with: pip install content-accessibility-utility-on-aws[rendered]"
            ) from e
        try:
            self._playwright = sync_playwright().start()
            self._browser = self._connect_browser(self._playwright)
        except Exception as e:
            # A partial connect (e.g. Playwright driver started, or a managed
            # AgentCore session started, then a later step threw) must not leak.
            # The caller reuses one probe across many pages and swallows
            # BrowserUnavailableError per page, so without cleanup here each
            # subsequent page would orphan another driver process / billable
            # session. Release whatever was started before propagating.
            self._teardown_partial()
            if isinstance(e, BrowserUnavailableError):
                raise
            raise BrowserUnavailableError(  # pragma: no cover - env dependent
                f"Could not obtain a headless browser: {e}"
            ) from e

    def _teardown_partial(self) -> None:
        """Undo a failed connect so a retry starts clean and nothing leaks."""
        try:
            if self._browser is not None:
                self._browser.close()
        except Exception:  # pragma: no cover - best effort
            pass
        self._browser = None
        try:
            if self._playwright is not None:
                self._playwright.stop()
        except Exception:  # pragma: no cover - best effort
            pass
        self._playwright = None
        # Let a subclass release its own backend (e.g. stop an AgentCore session).
        self._teardown()

    def _new_page(self, html: str):
        self._ensure_browser()
        page = self._browser.new_page(viewport=self._viewport)
        # If any setup step fails after the page is created, close it here — the
        # caller only wraps the returned page in a try/finally, so a page that
        # never gets returned would otherwise leak.
        try:
            # Disable animations/transitions for deterministic computed styles.
            page.add_init_script(
                "document.addEventListener('DOMContentLoaded', () => {"
                "const s = document.createElement('style');"
                "s.textContent = '*{animation:none!important;transition:none!important;}';"
                "document.head && document.head.appendChild(s);});"
            )
            page.set_content(html, wait_until="networkidle")
            # Drive the page into a requested runtime state (e.g. open a modal)
            # so the probe observes issues that only exist after interaction.
            # Failures here are non-fatal: probe the pristine page rather than
            # aborting, since a bad script should not block all detection.
            if self._setup_script:
                try:
                    page.evaluate(f"() => {{ {self._setup_script} }}")
                    page.wait_for_timeout(150)  # let state settle (deterministic)
                except Exception as e:  # pragma: no cover - script-dependent
                    logger.warning("set_state_script failed, probing pristine page: %s", e)
        except Exception:
            page.close()
            raise
        return page

    def set_state_script(self, script: Optional[str]) -> None:
        """Set (or clear, with None) the JS run after each render before probing."""
        self._setup_script = script or None

    def render_and_probe(self, html: str) -> ProbeResult:
        return self._submit(self._render_and_probe_impl, html)

    def get_element(self, html: str, selector: str) -> ElementInfo:
        return self._submit(self._get_element_impl, html, selector)

    def verify(self, html: str, selector: str, criterion: str) -> VerifyResult:
        return self._submit(self._verify_impl, html, selector, criterion)

    def _render_and_probe_impl(self, html: str) -> ProbeResult:
        page = self._new_page(html)
        try:
            page.evaluate(self._axe_js)
            axe_raw = page.evaluate("async () => await axe.run()")
            violations = _parse_axe_violations(axe_raw)
            focus_raw = page.evaluate(_FOCUS_PROBE_JS, FOCUSABLE_SELECTOR)
            focus_findings = [
                FocusFinding(
                    selector=f["selector"],
                    html=f["html"],
                    has_visible_indicator=f["has_visible_indicator"],
                    base_style=f["base_style"],
                    focus_style=f["focus_style"],
                )
                for f in focus_raw
            ]
            order_raw = page.evaluate(_FOCUS_ORDER_PROBE_JS)
            focus_order_findings = [
                FocusOrderFinding(
                    selector=f["selector"], html=f["html"], tabindex=f["tabindex"]
                )
                for f in order_raw
            ]
            return ProbeResult(
                violations=violations,
                focus_findings=focus_findings,
                focus_order_findings=focus_order_findings,
            )
        finally:
            page.close()

    def _get_element_impl(self, html: str, selector: str) -> ElementInfo:
        page = self._new_page(html)
        try:
            handle = page.query_selector(selector)
            if handle is None:
                return ElementInfo(found=False, selector=selector)
            info = page.evaluate(
                """(el) => {
                    const cs = getComputedStyle(el);
                    const rect = el.getBoundingClientRect();
                    const style = {};
                    for (const p of ['color','background-color','font-size',
                        'font-weight','outline-style','outline-width','display'])
                        style[p] = cs.getPropertyValue(p);
                    return {
                        tag: el.tagName.toLowerCase(),
                        outer_html: el.outerHTML.slice(0, 600),
                        computed_style: style,
                        bounding_box: {width: rect.width, height: rect.height},
                        role: el.getAttribute('role'),
                    };
                }""",
                handle,
            )
            name = None
            try:
                snap = page.accessibility.snapshot(root=handle)
                if snap:
                    name = snap.get("name")
            except Exception:  # pragma: no cover - a11y snapshot best effort
                pass
            return ElementInfo(
                found=True,
                selector=selector,
                tag=info["tag"],
                outer_html=info["outer_html"],
                computed_style=info["computed_style"],
                bounding_box=info["bounding_box"],
                accessible_name=name,
                role=info["role"],
            )
        finally:
            page.close()

    def _verify_impl(self, html: str, selector: str, criterion: str) -> VerifyResult:
        """Re-check one node against one criterion after a proposed fix.

        Only the criteria the rendered layer owns are handled here. An unknown
        criterion returns ``passed=False`` with an explanatory detail rather
        than silently claiming success.
        """
        if criterion == "2.4.7":
            return self._verify_focus_visible(html, selector)
        if criterion in ("1.4.3", "1.4.11"):
            return self._verify_contrast(html, selector, criterion)
        if criterion == "2.4.3":
            return self._verify_focus_order(html, selector)
        if criterion == "4.1.2":
            return self._verify_name_role_value(html, selector)
        return VerifyResult(
            criterion=criterion,
            selector=selector,
            passed=False,
            detail=f"No rendered verifier for criterion {criterion}",
        )

    def _verify_focus_visible(self, html: str, selector: str) -> VerifyResult:
        page = self._new_page(html)
        try:
            results = page.evaluate(_FOCUS_PROBE_JS, selector)
            if not results:
                return VerifyResult(
                    "2.4.7", selector, passed=False,
                    detail="Element not found when verifying focus indicator",
                )
            finding = results[0]
            passed = bool(finding["has_visible_indicator"])
            return VerifyResult(
                "2.4.7", selector, passed=passed,
                measured={"focus_style": finding["focus_style"]},
                detail=(
                    "Visible focus indicator present"
                    if passed
                    else "No visible focus indicator on focus"
                ),
            )
        finally:
            page.close()

    # axe rules that back WCAG 4.1.2 (Name, Role, Value) — the same rules the
    # adapter maps to accessible-name / aria-state / aria-structure issues. The
    # verifier re-runs exactly these, scoped to the node, so "fixed" means axe no
    # longer flags a name/role/value problem on it.
    _NRV_RULES = [
        "button-name", "link-name", "aria-command-name", "aria-toggle-field-name",
        "aria-input-field-name", "select-name", "aria-required-attr",
        "aria-required-parent", "aria-required-children", "aria-valid-attr-value",
    ]

    def _verify_name_role_value(self, html: str, selector: str) -> VerifyResult:
        """Re-run axe's Name/Role/Value rules scoped to one node (WCAG 4.1.2).

        Passes when none of the 4.1.2-backing rules flag the element. Confirms
        accessible-name, required-state, and required-structure fixes the agent
        applies, which previously had no verifier (so real fixes could not be
        marked resolved through the verify-gated commit).
        """
        page = self._new_page(html)
        try:
            match_count = page.evaluate(
                "(sel) => document.querySelectorAll(sel).length", selector
            )
            if not match_count:
                return VerifyResult(
                    "4.1.2", selector, passed=False,
                    detail="Element not found when verifying name/role/value",
                )
            page.evaluate(self._axe_js)
            axe_raw = page.evaluate(
                "async (args) => await axe.run(args.sel, {runOnly: args.rules})",
                {"sel": selector, "rules": self._NRV_RULES},
            )
            violations = _parse_axe_violations(axe_raw)
            failed = bool(violations)
            return VerifyResult(
                "4.1.2", selector, passed=not failed,
                measured={"violations": [v.rule_id for v in violations]},
                detail=(
                    "Name/role/value valid"
                    if not failed
                    else "Still flagged: " + ", ".join(v.rule_id for v in violations)
                ),
            )
        finally:
            page.close()

    def _verify_focus_order(self, html: str, selector: str) -> VerifyResult:
        """Pass when the element no longer carries a positive tabindex (2.4.3)."""
        page = self._new_page(html)
        try:
            ti = page.evaluate(
                """(sel) => {
                    const el = document.querySelector(sel);
                    if (!el) return null;
                    const v = el.getAttribute('tabindex');
                    return v === null ? 0 : parseInt(v, 10);
                }""",
                selector,
            )
            if ti is None:
                return VerifyResult(
                    "2.4.3", selector, passed=False,
                    detail="Element not found when verifying focus order",
                )
            passed = not (isinstance(ti, (int, float)) and ti > 0)
            return VerifyResult(
                "2.4.3", selector, passed=passed,
                measured={"tabindex": ti},
                detail=(
                    "No positive tabindex; focus follows DOM order"
                    if passed
                    else f"Element still has positive tabindex={ti}"
                ),
            )
        finally:
            page.close()

    def _verify_contrast(self, html: str, selector: str, criterion: str) -> VerifyResult:
        """Re-run axe's color-contrast rule scoped to a single node.

        The selector is expected to identify one element (the rendered audit
        emits axe's own unique node selector). If it resolves to no element the
        fix cannot be confirmed, so we report a failure rather than silently
        passing. axe is scoped to the element's own subtree, so only that
        node's text contrast is evaluated — a failing sibling elsewhere on the
        page does not fail this node.
        """
        page = self._new_page(html)
        try:
            match_count = page.evaluate(
                "(sel) => document.querySelectorAll(sel).length", selector
            )
            if not match_count:
                return VerifyResult(
                    criterion, selector, passed=False,
                    detail="Element not found when verifying contrast",
                )
            page.evaluate(self._axe_js)
            axe_raw = page.evaluate(
                "async (sel) => await axe.run(sel, {runOnly: ['color-contrast']})",
                selector,
            )
            violations = _parse_axe_violations(axe_raw)
            failed = bool(violations)
            return VerifyResult(
                criterion, selector, passed=not failed,
                detail=(
                    "Contrast meets threshold"
                    if not failed
                    else "Contrast still below threshold"
                ),
            )
        finally:
            page.close()

    def _close_impl(self) -> None:
        try:
            if self._browser is not None:
                self._browser.close()
        finally:
            self._browser = None
            if self._playwright is not None:
                self._playwright.stop()
                self._playwright = None
            # Release any subclass-owned backend (e.g. an AgentCore session).
            self._teardown()

    def _teardown(self) -> None:
        """Release subclass-owned resources. Runs on the browser thread."""

    def close(self) -> None:
        if self._executor is None:
            return
        try:
            self._submit(self._close_impl)
        finally:
            self._executor.shutdown(wait=True)
            self._executor = None


class LocalPlaywrightProbe(_PlaywrightProbeBase):
    """A ``BrowserProbe`` backed by a local headless Chromium via Playwright.

    For local development, CI, and the webapp. Requires the optional
    ``[rendered]`` extra and a Chromium binary (``playwright install chromium``).
    """

    def _connect_browser(self, playwright):
        try:
            return playwright.chromium.launch(headless=True)
        except Exception as e:  # pragma: no cover - environment dependent
            raise BrowserUnavailableError(
                f"Could not launch headless Chromium: {e}. Run "
                "'playwright install chromium' to install the browser binary."
            ) from e


class AgentCoreBrowserProbe(_PlaywrightProbeBase):
    """A ``BrowserProbe`` backed by the Amazon Bedrock AgentCore Browser Tool.

    This is the hosted-path counterpart to :class:`LocalPlaywrightProbe`. It
    starts a managed cloud browser session via the AgentCore SDK and connects
    Playwright to it over CDP, so **no Chromium binary ships in our artifact**.
    Because it subclasses :class:`_PlaywrightProbeBase`, every probe/verify
    behavior is byte-for-byte identical to the local probe — only how the
    browser handle is obtained differs. Choosing between the two is therefore a
    deployment config choice, not a code fork (see :func:`make_browser_probe`).

    Requires the optional ``[agent]`` extra plus the ``bedrock-agentcore`` SDK,
    and AWS credentials with AgentCore Browser permissions. The AgentCore region
    and browser identifier are configurable; the identifier defaults to the
    AWS-managed ``aws.browser.v1`` browser.
    """

    def __init__(
        self,
        region: Optional[str] = None,
        identifier: Optional[str] = None,
        session_timeout_seconds: int = 3600,
        viewport: Optional[Dict[str, int]] = None,
    ) -> None:
        super().__init__(viewport=viewport)
        self._region = region
        self._identifier = identifier
        self._session_timeout = session_timeout_seconds
        self._agentcore_client = None

    def _connect_browser(self, playwright):
        try:
            from bedrock_agentcore.tools.browser_client import BrowserClient
        except ImportError as e:
            raise BrowserUnavailableError(
                "The AgentCore SDK is not installed. Install it with: "
                "pip install content-accessibility-utility-on-aws[agent] "
                "bedrock-agentcore"
            ) from e

        region = self._region or _default_region()
        if not region:
            raise BrowserUnavailableError(
                "No AWS region configured for the AgentCore browser. Set "
                "AWS_REGION or pass region=... to AgentCoreBrowserProbe."
            )

        # Start a managed browser session, then connect Playwright to it over
        # the Chrome DevTools Protocol WebSocket the session exposes.
        client = BrowserClient(region=region)
        start_kwargs = {"session_timeout_seconds": self._session_timeout}
        if self._identifier:
            start_kwargs["identifier"] = self._identifier
        client.start(**start_kwargs)
        self._agentcore_client = client

        ws_url, headers = client.generate_ws_headers()
        return playwright.chromium.connect_over_cdp(ws_url, headers=headers)

    def _teardown(self) -> None:
        # Stop the managed session so it is not left running (it bills per time).
        if self._agentcore_client is not None:
            try:
                self._agentcore_client.stop()
            except Exception as e:  # pragma: no cover - best-effort cleanup
                logger.warning("Failed to stop AgentCore browser session: %s", e)
            finally:
                self._agentcore_client = None


def _default_region() -> Optional[str]:
    """Resolve the AWS region from the environment (AgentCore needs one)."""
    return os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")


def make_browser_probe(options: Optional[Dict[str, Any]] = None) -> BrowserProbe:
    """Return the browser probe appropriate for the current deployment.

    A single factory so callers (CLI, webapp, batch) never hard-code which
    backend to use — deployment becomes configuration:

    - ``options["browser_backend"] == "agentcore"`` (or env
      ``A11Y_BROWSER_BACKEND=agentcore``) → managed AgentCore browser.
    - otherwise → local Playwright Chromium.

    The two satisfy the same :class:`BrowserProbe` interface, so everything
    above the probe is unchanged regardless of which one is returned.
    """
    options = options or {}
    backend = (
        options.get("browser_backend")
        or os.environ.get("A11Y_BROWSER_BACKEND")
        or "local"
    ).lower()

    if backend == "agentcore":
        return AgentCoreBrowserProbe(
            region=options.get("agentcore_region"),
            identifier=options.get("agentcore_browser_id"),
        )
    return LocalPlaywrightProbe()


def _parse_axe_violations(axe_raw: Dict[str, Any]) -> List[RawViolation]:
    """Convert the raw ``axe.run()`` result object into typed violations."""
    out: List[RawViolation] = []
    for v in (axe_raw or {}).get("violations", []):
        nodes = [
            RawViolationNode(
                # axe's ``target`` is a list of selectors (one per frame); the
                # last element is the selector within the final document.
                target=(n.get("target") or [""])[-1],
                html=n.get("html", ""),
                failure_summary=n.get("failureSummary", ""),
            )
            for n in v.get("nodes", [])
        ]
        out.append(
            RawViolation(
                rule_id=v.get("id", ""),
                impact=v.get("impact"),
                description=v.get("description", ""),
                help=v.get("help", ""),
                help_url=v.get("helpUrl", ""),
                wcag_tags=[t for t in v.get("tags", []) if t.startswith("wcag")],
                nodes=nodes,
            )
        )
    return out
