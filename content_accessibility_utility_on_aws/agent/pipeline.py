# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Managed accessibility pipeline (deployment-agnostic core).

This module holds the pipeline logic the AgentCore Runtime entrypoint invokes.
It lives in the installed package (not in the deployment scaffold) so the repo
``deployment/`` copy and the bundled ``deployment_assets/`` copy are both thin
wrappers around the SAME code and cannot drift.

Prefix-routed:
    pdf/<name>.pdf            -> convert (PDF->HTML bundle) + manifest.json
    html/<name>.html|.zip     -> audit + agent-remediate
    html/<name>/manifest.json -> audit + agent-remediate (converted bundle)

Two behaviors matter for real, large documents:

- **Idempotency.** AgentCore Runtime may retry a long invocation; without a
  guard, a multi-hundred-page document would be reprocessed from scratch each
  time. :func:`run_pipeline` skips work when the job for this input is already
  recorded COMPLETE.

- **Bounded per-page agent (multi-page docs).** The static audit/remediate runs
  over the whole bundle. The browser-backed **agent** — which catches computed
  contrast, focus visibility, name-role-value, and authors multimodal alt text —
  is expensive per page (a managed browser session + model loop each), so it is
  run only on *candidate* pages (those containing interactive elements or
  images), capped by ``max_agent_pages``. Text/table pages the static path
  already handles are skipped. This keeps the agent's value without running
  hundreds of browser sessions on a single report.
"""

from __future__ import annotations

import json
import os
import tempfile
import zipfile
from typing import Any, Dict, List, Optional, Tuple

from content_accessibility_utility_on_aws.api import (
    audit_html_accessibility,
    convert_pdf_to_html,
    remediate_html_accessibility,
)
from content_accessibility_utility_on_aws.batch.common import (
    STAGE_COMPLETE,
    STAGE_PDF_TO_HTML,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_PROCESSING,
    create_job_record,
    generate_job_id,
    get_job_status,
    s3_client,
    update_job_status,
)
from content_accessibility_utility_on_aws.batch.pdf2html import upload_conversion_results
from content_accessibility_utility_on_aws.utils.logging_helper import setup_logger

logger = setup_logger(__name__)

# The rendered/agent layer targets the managed AgentCore browser by default
# (there is no local Chromium in the runtime artifact).
DEFAULT_OPTIONS: Dict[str, Any] = {
    "rendered": True,
    "agent": True,
    "browser_backend": "agentcore",
    "auto_fix": True,
    # Cap on how many pages of a multi-page document get the (expensive) agent
    # pass. Override via payload options or the A11Y_MAX_AGENT_PAGES env var.
    "max_agent_pages": 25,
}

PDF_PREFIX = "pdf/"
HTML_PREFIX = "html/"
OUTPUT_PREFIX = "accessible/"
MANIFEST_NAME = "manifest.json"


def run_pipeline(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Route one uploaded object through the pipeline. The entrypoint calls this."""
    input_bucket = payload.get("input_bucket")
    input_key = payload.get("input_key")
    if not input_bucket or not input_key:
        return {"status": "error", "error": "payload requires input_bucket and input_key"}

    output_bucket = payload.get("output_bucket") or input_bucket
    mode = payload.get("mode") or _infer_mode(input_key)

    options = dict(DEFAULT_OPTIONS)
    options.update(payload.get("options") or {})
    options.setdefault(
        "agentcore_region",
        os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION"),
    )
    env_cap = os.environ.get("A11Y_MAX_AGENT_PAGES")
    if env_cap and env_cap.isdigit():
        options["max_agent_pages"] = int(env_cap)

    job_id = payload.get("job_id") or generate_job_id(input_bucket, input_key)

    # Idempotency: if this exact input already finished, don't redo the work
    # (AgentCore may retry long invocations). ``force`` bypasses the guard.
    if not payload.get("force") and _already_complete(job_id):
        logger.info("Skip: job=%s already COMPLETE for s3://%s/%s",
                    job_id, input_bucket, input_key)
        return {"status": "skipped", "job_id": job_id, "reason": "already complete"}

    logger.info("Pipeline start: mode=%s job=%s s3://%s/%s",
                mode, job_id, input_bucket, input_key)
    try:
        create_job_record(job_id, document_key=input_key)
        if mode == "convert":
            return _run_convert(job_id, input_bucket, input_key, output_bucket, options)
        if mode == "audit":
            return _run_audit(job_id, input_bucket, input_key, output_bucket, options)
        return {"status": "error", "job_id": job_id, "error": f"unknown mode: {mode}"}
    except Exception as e:  # keep the runtime invocation itself successful
        logger.exception("Pipeline failed: job=%s", job_id)
        try:
            update_job_status(job_id, status=STATUS_FAILED, stage="PIPELINE",
                              details={"error": str(e)})
        except Exception:  # pragma: no cover
            pass
        return {"status": "error", "job_id": job_id, "error": str(e)}


def _already_complete(job_id: str) -> bool:
    """True if a prior run recorded this job as COMPLETE (idempotency guard)."""
    try:
        record = get_job_status(job_id)
    except Exception:
        return False  # no record (or table error) -> proceed
    return (
        record.get("status") == STATUS_COMPLETED
        and record.get("stage") == STAGE_COMPLETE
    )


def _infer_mode(input_key: str) -> str:
    if input_key.startswith(PDF_PREFIX):
        return "convert"
    return "audit"


# ---------------------------------------------------------------------------
# Convert stage: PDF -> HTML bundle + manifest
# ---------------------------------------------------------------------------

def _run_convert(
    job_id: str, input_bucket: str, input_key: str, output_bucket: str, options: Dict[str, Any]
) -> Dict[str, Any]:
    update_job_status(job_id, STATUS_PROCESSING, STAGE_PDF_TO_HTML, {"input_key": input_key})

    with tempfile.TemporaryDirectory() as tmp:
        pdf_path = os.path.join(tmp, os.path.basename(input_key))
        s3_client.download_file(input_bucket, input_key, pdf_path)

        out_dir = os.path.join(tmp, "output")
        os.makedirs(out_dir, exist_ok=True)
        result = convert_pdf_to_html(pdf_path=pdf_path, output_dir=out_dir, options=options)

        s3_results = upload_conversion_results(result, input_key, output_bucket)

        base = os.path.splitext(os.path.basename(input_key))[0]
        bundle_prefix = f"{HTML_PREFIX}{base}/"
        manifest = {
            "source_key": input_key,
            "html_key": s3_results["html_key"],
            "html_files": s3_results.get("html_files", []),
            "image_files": s3_results.get("image_files", []),
            "css_files": s3_results.get("css_files", []),
            "multi_page": bool(s3_results.get("html_files")),
        }
        manifest_key = f"{bundle_prefix}{MANIFEST_NAME}"
        # Manifest LAST: the audit trigger fires on it, guaranteeing all assets
        # are present.
        s3_client.put_object(
            Bucket=output_bucket, Key=manifest_key,
            Body=json.dumps(manifest).encode("utf-8"),
            ContentType="application/json",
        )

    update_job_status(
        job_id, STATUS_COMPLETED, STAGE_PDF_TO_HTML,
        {"html_key": manifest["html_key"], "manifest_key": manifest_key},
    )
    logger.info("Convert complete: job=%s manifest=s3://%s/%s", job_id, output_bucket, manifest_key)
    return {
        "status": "completed", "stage": "convert", "job_id": job_id,
        "manifest_key": manifest_key, "html_key": manifest["html_key"],
    }


# ---------------------------------------------------------------------------
# Audit stage: single html / zip / converted bundle -> accessible output
# ---------------------------------------------------------------------------

def _run_audit(
    job_id: str, input_bucket: str, input_key: str, output_bucket: str, options: Dict[str, Any]
) -> Dict[str, Any]:
    from content_accessibility_utility_on_aws.batch.common import STAGE_AUDIT

    update_job_status(job_id, STATUS_PROCESSING, STAGE_AUDIT, {"input_key": input_key})

    with tempfile.TemporaryDirectory() as tmp:
        work = os.path.join(tmp, "html")
        os.makedirs(work, exist_ok=True)

        audit_target, multi_page, name = _materialize_html_input(
            input_bucket, input_key, work
        )
        if multi_page:
            options = {**options, "multi_page": True}

        audit_report = os.path.join(tmp, "audit.json")
        audit_result = audit_html_accessibility(
            html_path=audit_target, image_dir=work, options=options, output_path=audit_report
        )

        agent_pages = 0
        if multi_page:
            # Static remediation over the whole bundle (in place).
            remediate_html_accessibility(
                html_path=audit_target, audit_report=audit_result,
                output_path=audit_target, image_dir=work, options=options,
            )
            # Then the bounded per-page agent pass on candidate pages only —
            # pages the audit flagged with issues the browser agent can improve.
            agent_pages = _run_agent_on_candidate_pages(work, options, audit_result)
            publish_root = work
            reaudit_target = audit_target
        else:
            remediated_file = os.path.join(work, f"{name}.remediated.html")
            remediate_html_accessibility(
                html_path=audit_target, audit_report=audit_result,
                output_path=remediated_file, image_dir=work, options=options,
            )
            if os.path.abspath(audit_target) != os.path.abspath(remediated_file):
                try:
                    os.remove(audit_target)
                except OSError:
                    pass
            # Browser-backed agent pass on the single remediated page, when the
            # audit flagged an agent-relevant issue (computed contrast, focus,
            # name-role-value, …) the static path cannot resolve. Interactive
            # single-file HTML (dashboards, widgets) is the agent's core case.
            agent_pages = _run_agent_on_single_page(
                remediated_file, options, audit_result
            )
            publish_root = work
            reaudit_target = remediated_file

        # Re-audit the FINAL remediated HTML so the published report reflects
        # what static + agent actually fixed — not just the pre-remediation
        # state. Without this, the report always shows the original issues
        # ("agent on N pages" in the log but a report that credits nothing),
        # which makes the residual gap impossible to measure. Non-fatal.
        final_report = os.path.join(tmp, "audit_after.json")
        gap = _reaudit_final(
            reaudit_target, work, options, audit_result, final_report
        )

        out_prefix = f"{OUTPUT_PREFIX}{name}/"
        published = _publish_tree(publish_root, output_bucket, out_prefix)
        # Publish the BEFORE report (original findings) and, when the re-audit
        # succeeded, the AFTER report (residual findings) + a gap summary.
        if os.path.isfile(audit_report):
            s3_client.upload_file(
                audit_report, output_bucket, f"{out_prefix}accessibility_audit_before.json"
            )
            published.append(f"{out_prefix}accessibility_audit_before.json")
        if os.path.isfile(final_report):
            # The canonical report name now points at the post-remediation state.
            s3_client.upload_file(
                final_report, output_bucket, f"{out_prefix}accessibility_audit.json"
            )
            published.append(f"{out_prefix}accessibility_audit.json")
        elif os.path.isfile(audit_report):
            # Re-audit unavailable (e.g. no browser): fall back to the before
            # report under the canonical name so a report is always published.
            s3_client.upload_file(
                audit_report, output_bucket, f"{out_prefix}accessibility_audit.json"
            )
            published.append(f"{out_prefix}accessibility_audit.json")
        if gap is not None:
            gap_path = os.path.join(tmp, "remediation_gap.json")
            with open(gap_path, "w", encoding="utf-8") as fh:
                json.dump(gap, fh, indent=2)
            s3_client.upload_file(
                gap_path, output_bucket, f"{out_prefix}remediation_gap.json"
            )
            published.append(f"{out_prefix}remediation_gap.json")

    status_detail = {
        "output_prefix": out_prefix, "output_bucket": output_bucket,
        "files": len(published), "agent_pages": agent_pages,
    }
    if gap is not None:
        status_detail["issues_before"] = gap["issues_before"]
        status_detail["issues_after"] = gap["issues_after"]
        status_detail["issues_resolved"] = gap["issues_resolved"]
    update_job_status(job_id, STATUS_COMPLETED, STAGE_COMPLETE, status_detail)
    if gap is not None:
        logger.info(
            "Audit+remediate complete: job=%s -> s3://%s/%s (%d files, agent on %d "
            "pages, %d->%d issues, %d resolved)",
            job_id, output_bucket, out_prefix, len(published), agent_pages,
            gap["issues_before"], gap["issues_after"], gap["issues_resolved"],
        )
    else:
        logger.info(
            "Audit+remediate complete: job=%s -> s3://%s/%s (%d files, agent on %d pages)",
            job_id, output_bucket, out_prefix, len(published), agent_pages,
        )
    return {
        "status": "completed", "stage": "audit", "job_id": job_id,
        "output_bucket": output_bucket, "output_prefix": out_prefix,
        "published_keys": published, "agent_pages": agent_pages,
        "total_issues": audit_result.get("summary", {}).get("total_issues"),
    }


# WCAG success criteria whose issues the browser-backed agent can actually
# improve beyond the static path: things that need a rendered page — computed
# contrast, focus visibility/order, name-role-value on custom widgets, ARIA
# state, status messages, and target size. A page is only worth the (expensive)
# per-page browser+agent pass if the audit flagged one of these on it. Pure
# structural issues (headings, tables, landmarks, language, titles) are fully
# handled by the static remediation, so those pages are skipped.
_AGENT_RELEVANT_WCAG = {
    "1.4.3",   # Contrast (Minimum)
    "1.4.11",  # Non-text Contrast
    "2.4.7",   # Focus Visible
    "2.4.3",   # Focus Order
    "2.1.1",   # Keyboard
    "2.1.2",   # No Keyboard Trap
    "2.5.8",   # Target Size (Minimum)
    "4.1.2",   # Name, Role, Value
    "4.1.3",   # Status Messages
}


def _reaudit_final(
    audit_target: str,
    work_dir: str,
    options: Dict[str, Any],
    before_result: Dict[str, Any],
    output_path: str,
) -> Optional[Dict[str, Any]]:
    """Re-audit the final remediated HTML and return a before/after gap summary.

    Runs the SAME audit (static + rendered, per ``options``) against the
    post-remediation document so the published report reflects what was actually
    fixed. Returns a dict with before/after issue counts, per-criterion residual
    counts, and the resolved delta — or ``None`` if the re-audit could not run
    (never fatal; the caller falls back to the before report).
    """
    try:
        after_result = audit_html_accessibility(
            html_path=audit_target, image_dir=work_dir,
            options=options, output_path=output_path,
        )
    except Exception as e:  # pragma: no cover - re-audit is best-effort
        logger.warning("Post-remediation re-audit failed: %s", e)
        return None

    def _open_count(result: Dict[str, Any]) -> int:
        summary = result.get("summary") or {}
        if "needs_remediation" in summary:
            return int(summary.get("needs_remediation") or 0)
        # Fall back to counting unresolved issues directly.
        return sum(
            1 for i in result.get("issues", [])
            if i.get("remediation_status") not in ("compliant", "remediated", "resolved")
        )

    def _by_criterion(result: Dict[str, Any]) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for i in result.get("issues", []):
            if i.get("remediation_status") in ("compliant", "remediated", "resolved"):
                continue
            crit = i.get("wcag_criterion") or "unknown"
            counts[crit] = counts.get(crit, 0) + 1
        return dict(sorted(counts.items()))

    before_open = _open_count(before_result)
    after_open = _open_count(after_result)
    return {
        "issues_before": before_open,
        "issues_after": after_open,
        "issues_resolved": max(0, before_open - after_open),
        "residual_by_criterion": _by_criterion(after_result),
        "before_by_criterion": _by_criterion(before_result),
    }


# Largest single linked asset we will inline into the HTML (bytes). Keeps a
# pathological stylesheet/script from bloating the payload sent to the remote
# browser; anything larger is left as an external reference (and simply won't be
# rendered by the probe, as before).
_MAX_INLINE_ASSET_BYTES = 2_000_000


def _inline_local_assets(html: str, base_dir: str) -> str:
    """Inline linked *local* CSS/JS into the HTML so a browser probe renders it.

    The agent's probe renders an HTML *string* (via ``page.set_content``) with no
    base URL — and in the hosted path the browser is a remote managed service
    with no access to our filesystem. Either way, relative ``<link href>`` /
    ``<script src>`` assets never load, so computed-style and interactive issues
    defined in external CSS/JS (focus outlines, class-based contrast, widget
    behavior) are invisible to axe and the focus probe. Inlining those assets
    into the document makes them part of what the probe renders.

    Only same-origin *relative* paths that resolve inside ``base_dir`` are
    inlined; absolute URLs (``http(s)://``, protocol-relative ``//``, ``data:``)
    are left untouched. Returns the HTML unchanged if there is nothing to inline
    or BeautifulSoup is unavailable.
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:  # pragma: no cover - bs4 is a core dep
        return html

    def _local_path(ref: str) -> Optional[str]:
        if not ref:
            return None
        low = ref.strip().lower()
        if low.startswith(("http://", "https://", "//", "data:", "#", "mailto:")):
            return None
        # Resolve relative to base_dir and confine to it (no path traversal).
        candidate = os.path.normpath(os.path.join(base_dir, ref.split("?", 1)[0]))
        base_abs = os.path.abspath(base_dir)
        if os.path.commonpath([base_abs, os.path.abspath(candidate)]) != base_abs:
            return None
        return candidate if os.path.isfile(candidate) else None

    def _read(path: str) -> Optional[str]:
        try:
            if os.path.getsize(path) > _MAX_INLINE_ASSET_BYTES:
                return None
            with open(path, "r", encoding="utf-8") as fh:
                return fh.read()
        except OSError:
            return None

    soup = BeautifulSoup(html, "html.parser")
    changed = False

    for link in soup.find_all("link"):
        rels = [r.lower() for r in (link.get("rel") or [])]
        if "stylesheet" not in rels:
            continue
        path = _local_path(link.get("href", ""))
        css = _read(path) if path else None
        if css is None:
            continue
        style = soup.new_tag("style")
        style.string = css
        link.replace_with(style)
        changed = True

    for script in soup.find_all("script", src=True):
        path = _local_path(script.get("src", ""))
        js = _read(path) if path else None
        if js is None:
            continue
        new_script = soup.new_tag("script")
        new_script.string = js
        script.replace_with(new_script)
        changed = True

    return str(soup) if changed else html


def _run_agent_on_candidate_pages(
    work_dir: str, options: Dict[str, Any], audit_result: Optional[Dict[str, Any]] = None
) -> int:
    """Run the browser-backed agent on multi-page docs, bounded to candidates.

    Candidates are the pages the audit flagged with an *agent-relevant* issue
    (computed contrast, focus, name-role-value, target size, …) that the static
    path cannot resolve — not merely pages that happen to contain a link or
    image. This keeps the per-page browser+agent cost spent only where it can
    pay off. Capped by ``max_agent_pages``. Returns the number of pages the
    agent actually changed. Any failure (browser unavailable, model error) is
    non-fatal: the statically-remediated page is left as-is.
    """
    if not (options.get("agent") or options.get("rendered")):
        return 0

    cap = int(options.get("max_agent_pages", 0) or 0)
    if cap <= 0:
        return 0

    candidates = _candidate_pages(work_dir, cap, audit_result)
    if not candidates:
        logger.info("No pages have agent-relevant findings; skipping agent pass")
        return 0

    # Import here so the core package never hard-depends on the agent stack.
    try:
        from content_accessibility_utility_on_aws.agent.browser_probe import (
            BrowserUnavailableError,
            make_browser_probe,
        )
        from content_accessibility_utility_on_aws.agent.agent import run_agent
    except ImportError as e:
        logger.warning("Agent layer unavailable, skipping per-page agent: %s", e)
        return 0

    processed = 0
    try:
        with make_browser_probe(options) as probe:
            for page_path in candidates:
                try:
                    with open(page_path, "r", encoding="utf-8") as f:
                        raw = f.read()
                    # Inline linked local CSS/JS so the probe renders the real
                    # computed cascade (external assets never load in the probe).
                    html = _inline_local_assets(raw, os.path.dirname(page_path))
                    result = run_agent(probe, html, options=options)
                    fixed = result.get("html")
                    # Persist the agent's output when it actually changed the
                    # page. We intentionally do NOT gate on result["resolved"]:
                    # the agent can apply many verified edits without the commit
                    # ledger capturing every one, and discarding a changed-and-
                    # improved page because the ledger is empty would throw away
                    # real fixes. The rendered layer's own verify() already
                    # guards fix *quality*; here we just avoid a no-op rewrite.
                    if fixed and fixed != html:
                        with open(page_path, "w", encoding="utf-8") as f:
                            f.write(fixed)
                        processed += 1
                except Exception as e:  # pragma: no cover - per-page resilience
                    logger.warning("Agent failed on %s: %s", os.path.basename(page_path), e)
    except BrowserUnavailableError as e:
        logger.warning("Browser unavailable, skipping per-page agent: %s", e)
        return 0
    except Exception as e:  # pragma: no cover
        logger.warning("Per-page agent pass failed: %s", e)
        return processed

    logger.info("Agent changed %d/%d candidate pages", processed, len(candidates))
    return processed


def _run_agent_on_single_page(
    page_path: str, options: Dict[str, Any], audit_result: Optional[Dict[str, Any]] = None
) -> int:
    """Run the browser-backed agent on a single remediated HTML file.

    Runs only when the rendered/agent layer is enabled and the audit flagged at
    least one *agent-relevant* issue (see :data:`_AGENT_RELEVANT_WCAG`) that the
    static path cannot resolve. Returns 1 if the agent changed the page, else 0.
    Any failure (browser unavailable, model error, missing agent stack) is
    non-fatal: the statically-remediated page is left in place.
    """
    if not (options.get("agent") or options.get("rendered")):
        return 0
    if int(options.get("max_agent_pages", 0) or 0) <= 0:
        return 0

    # Consult the audit: only pay the browser+agent cost when there is an
    # agent-relevant finding. When no audit result is available, fall back to a
    # DOM interactive-control heuristic so the function is usable standalone.
    if audit_result and audit_result.get("issues"):
        if not _has_agent_relevant_issue(audit_result):
            logger.info("No agent-relevant findings on page; skipping agent pass")
            return 0

    try:
        from content_accessibility_utility_on_aws.agent.browser_probe import (
            BrowserUnavailableError,
            make_browser_probe,
        )
        from content_accessibility_utility_on_aws.agent.agent import run_agent
    except ImportError as e:
        logger.warning("Agent layer unavailable, skipping single-page agent: %s", e)
        return 0

    try:
        with open(page_path, "r", encoding="utf-8") as f:
            raw = f.read()
    except OSError as e:
        logger.warning("Could not read page for agent pass: %s", e)
        return 0

    # Inline linked local CSS/JS so the probe renders the real computed cascade
    # (external assets do not load in a set_content / remote-browser render).
    html = _inline_local_assets(raw, os.path.dirname(page_path))

    try:
        with make_browser_probe(options) as probe:
            result = run_agent(probe, html, options=options)
    except BrowserUnavailableError as e:
        logger.warning("Browser unavailable, skipping single-page agent: %s", e)
        return 0
    except Exception as e:  # pragma: no cover - resilience
        logger.warning("Single-page agent pass failed: %s", e)
        return 0

    fixed = result.get("html")
    # Persist only when the agent actually changed the page (see the multi-page
    # path for why we do not gate on result["resolved"]).
    if fixed and fixed != html:
        try:
            with open(page_path, "w", encoding="utf-8") as f:
                f.write(fixed)
            logger.info("Agent changed the single page")
            return 1
        except OSError as e:  # pragma: no cover
            logger.warning("Could not write agent output: %s", e)
    return 0


def _candidate_pages(
    work_dir: str, cap: int, audit_result: Optional[Dict[str, Any]] = None
) -> List[str]:
    """Select up to ``cap`` pages the audit flagged with agent-relevant issues.

    Uses the audit findings (each carries ``file_name``/``page_number``) to pick
    only pages with an unresolved issue in :data:`_AGENT_RELEVANT_WCAG`. Falls
    back to a DOM heuristic (pages with interactive controls) only when no audit
    result is available, so the function is still usable standalone.
    """
    html_files = sorted(
        os.path.join(r, f)
        for r, _d, files in os.walk(work_dir)
        for f in files
        if f.lower().endswith((".html", ".htm"))
    )

    if audit_result and audit_result.get("issues"):
        flagged = _pages_with_agent_relevant_issues(audit_result)
        if flagged:
            matched = [
                p for p in html_files if os.path.basename(p) in flagged
            ]
            return matched[:cap]
        # Audit ran but flagged nothing agent-relevant → nothing to do.
        return []

    # Fallback: no audit result to consult — use a DOM heuristic.
    from bs4 import BeautifulSoup

    interactive = ("a", "button", "input", "select", "textarea", "img")
    candidates: List[str] = []
    for path in html_files:
        try:
            with open(path, "r", encoding="utf-8") as fh:
                soup = BeautifulSoup(fh.read(), "html.parser")
        except OSError:
            continue
        if soup.find(interactive):
            candidates.append(path)
            if len(candidates) >= cap:
                break
    return candidates


def _pages_with_agent_relevant_issues(audit_result: Dict[str, Any]) -> set:
    """Set of page file names that have an unresolved agent-relevant issue."""
    flagged = set()
    for issue in audit_result.get("issues", []):
        if issue.get("wcag_criterion") not in _AGENT_RELEVANT_WCAG:
            continue
        if issue.get("remediation_status") == "compliant":
            continue
        loc = issue.get("location") or {}
        fname = issue.get("file_name") or loc.get("file_name")
        if fname:
            flagged.add(os.path.basename(fname))
    return flagged


def _has_agent_relevant_issue(audit_result: Dict[str, Any]) -> bool:
    """True if the audit has any unresolved agent-relevant issue (any page).

    Used by the single-page path, where there is exactly one document so a
    per-file-name match is unnecessary — we only need to know whether the agent
    could add value at all.
    """
    for issue in audit_result.get("issues", []):
        if issue.get("wcag_criterion") not in _AGENT_RELEVANT_WCAG:
            continue
        if issue.get("remediation_status") == "compliant":
            continue
        return True
    return False


# ---------------------------------------------------------------------------
# Input materialization (single html / zip / bundle)
# ---------------------------------------------------------------------------

def _materialize_html_input(
    bucket: str, key: str, work_dir: str
) -> Tuple[str, bool, str]:
    fname = os.path.basename(key)

    if fname == MANIFEST_NAME:
        name = (
            key[len(HTML_PREFIX):].rstrip("/").rsplit("/", 1)[0]
            if key.startswith(HTML_PREFIX) else "document"
        )
        return _materialize_bundle(bucket, key, work_dir, name)

    if fname.lower().endswith(".zip"):
        name = os.path.splitext(fname)[0]
        local_zip = os.path.join(work_dir, fname)
        s3_client.download_file(bucket, key, local_zip)
        with zipfile.ZipFile(local_zip) as zf:
            _safe_extract_zip(zf, work_dir)
        os.remove(local_zip)
        return _pick_html_target(work_dir, name)

    name = os.path.splitext(fname)[0]
    local_html = os.path.join(work_dir, fname)
    s3_client.download_file(bucket, key, local_html)
    return local_html, False, name


def _bundle_dest(work_dir: str, bundle_prefix: str, key: str) -> str:
    """Resolve a manifest S3 ``key`` to a local path confined to ``work_dir``.

    The manifest is attacker-controllable (any object named ``manifest.json``
    uploaded under ``html/`` is routed here — the router does not verify the
    pipeline produced it), and its key values flow into a local write target, so
    they must be confined exactly like the zip and asset-inlining paths in this
    module. S3 keys are opaque strings that may contain ``..`` segments, so a
    key such as ``html/x/../../../../tmp/evil.py`` would otherwise escape
    ``work_dir``. Rejects any key that resolves outside ``work_dir``.
    """
    rel = key[len(bundle_prefix):] if key.startswith(bundle_prefix) else os.path.basename(key)
    work_root = os.path.realpath(work_dir)
    dest = os.path.realpath(os.path.join(work_dir, rel))
    if dest != work_root and not dest.startswith(work_root + os.sep):
        raise ValueError(f"Unsafe manifest key (path traversal): {key}")
    return dest


def _materialize_bundle(bucket: str, manifest_key: str, work_dir: str, name: str) -> Tuple[str, bool, str]:
    obj = s3_client.get_object(Bucket=bucket, Key=manifest_key)
    manifest = json.loads(obj["Body"].read())
    bundle_prefix = manifest_key.rsplit("/", 1)[0] + "/"

    keys: List[str] = [manifest["html_key"]]
    keys += manifest.get("html_files", [])
    keys += manifest.get("image_files", [])
    keys += manifest.get("css_files", [])

    for k in keys:
        dest = _bundle_dest(work_dir, bundle_prefix, k)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        s3_client.download_file(bucket, k, dest)

    multi_page = bool(manifest.get("multi_page"))
    if multi_page:
        return work_dir, True, name
    return _bundle_dest(work_dir, bundle_prefix, manifest["html_key"]), False, name


def _safe_extract_zip(zf: zipfile.ZipFile, dest_dir: str) -> None:
    """Extract a zip, rejecting entries that escape ``dest_dir`` (zip-slip)."""
    dest_root = os.path.realpath(dest_dir)
    for member in zf.namelist():
        target = os.path.realpath(os.path.join(dest_dir, member))
        if target != dest_root and not target.startswith(dest_root + os.sep):
            raise ValueError(f"Unsafe path in zip (path traversal): {member}")
    zf.extractall(dest_dir)


def _pick_html_target(work_dir: str, name: str) -> Tuple[str, bool, str]:
    html_files = []
    for root, _dirs, files in os.walk(work_dir):
        for f in files:
            if f.lower().endswith(".html"):
                html_files.append(os.path.join(root, f))
    if not html_files:
        raise ValueError("Zip contained no .html files to audit")
    if len(html_files) > 1:
        return work_dir, True, name
    return html_files[0], False, name


def _publish_tree(local_dir: str, bucket: str, out_prefix: str) -> List[str]:
    published: List[str] = []
    for root, _dirs, files in os.walk(local_dir):
        for f in files:
            local_path = os.path.join(root, f)
            rel = os.path.relpath(local_path, local_dir)
            key = f"{out_prefix}{rel}".replace(os.sep, "/")
            s3_client.upload_file(local_path, bucket, key)
            published.append(key)
    return published
