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
            publish_root = work

        out_prefix = f"{OUTPUT_PREFIX}{name}/"
        published = _publish_tree(publish_root, output_bucket, out_prefix)
        if os.path.isfile(audit_report):
            s3_client.upload_file(
                audit_report, output_bucket, f"{out_prefix}accessibility_audit.json"
            )
            published.append(f"{out_prefix}accessibility_audit.json")

    update_job_status(
        job_id, STATUS_COMPLETED, STAGE_COMPLETE,
        {"output_prefix": out_prefix, "output_bucket": output_bucket,
         "files": len(published), "agent_pages": agent_pages},
    )
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
                        html = f.read()
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


def _materialize_bundle(bucket: str, manifest_key: str, work_dir: str, name: str) -> Tuple[str, bool, str]:
    obj = s3_client.get_object(Bucket=bucket, Key=manifest_key)
    manifest = json.loads(obj["Body"].read())
    bundle_prefix = manifest_key.rsplit("/", 1)[0] + "/"

    keys: List[str] = [manifest["html_key"]]
    keys += manifest.get("html_files", [])
    keys += manifest.get("image_files", [])
    keys += manifest.get("css_files", [])

    for k in keys:
        rel = k[len(bundle_prefix):] if k.startswith(bundle_prefix) else os.path.basename(k)
        dest = os.path.join(work_dir, rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        s3_client.download_file(bucket, k, dest)

    multi_page = bool(manifest.get("multi_page"))
    if multi_page:
        return work_dir, True, name
    main_rel = manifest["html_key"]
    main_rel = main_rel[len(bundle_prefix):] if main_rel.startswith(bundle_prefix) else os.path.basename(main_rel)
    return os.path.join(work_dir, main_rel), False, name


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
