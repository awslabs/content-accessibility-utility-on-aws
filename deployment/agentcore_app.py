# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
AgentCore Runtime entrypoint for the managed accessibility pipeline.

Amazon Bedrock AgentCore Runtime hosts this module. A trigger Lambda invokes it
when an object is uploaded to the input bucket. The pipeline is prefix-routed:

    pdf/<name>.pdf          -> mode "convert": PDF -> HTML (via BDA), written to
                               html/<name>/ as a bundle, then a manifest.json
                               marker is written last (which re-triggers audit).
    html/<name>/manifest.json (or a single html/<name>.html, or html/<name>.zip)
                            -> mode "audit": audit + agent-remediate, output to
                               accessible/<name>/.

Why a manifest marker for the converted bundle: PDF conversion emits many S3
objects (document.html + images/ + css/), and each upload fires its own S3
event. Triggering audit on a single manifest.json written *after* all assets
guarantees one audit per document with every asset present — the robust answer
to multi-file, event-driven processing. HTML uploaded directly (single file or
zip) is audited immediately; no manifest is required for those.

The audit stage accepts three input shapes, all normalized to a local directory
before auditing:
  - a single .html file,
  - a .zip of HTML+CSS+JS,
  - a converted multi-file bundle described by manifest.json.

Payload contract:
    {
      "mode":          "convert" | "audit",   # optional; inferred from input_key
      "input_bucket":  "...",
      "input_key":     "...",                  # the object that triggered this
      "output_bucket": "...",                  # optional; defaults to input_bucket
      "options":       { ... }                 # optional pipeline options
    }
"""

from __future__ import annotations

import json
import os
import tempfile
import zipfile
from typing import Any, Dict, List, Optional, Tuple

from bedrock_agentcore.runtime import BedrockAgentCoreApp

from content_accessibility_utility_on_aws.api import (
    audit_html_accessibility,
    convert_pdf_to_html,
    remediate_html_accessibility,
)
from content_accessibility_utility_on_aws.batch.common import (
    STAGE_AUDIT,
    STAGE_COMPLETE,
    STAGE_PDF_TO_HTML,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_PROCESSING,
    create_job_record,
    generate_job_id,
    s3_client,
    update_job_status,
)
from content_accessibility_utility_on_aws.batch.pdf2html import upload_conversion_results
from content_accessibility_utility_on_aws.utils.logging_helper import setup_logger

logger = setup_logger(__name__)

app = BedrockAgentCoreApp()

# The rendered/agent layer must target the managed AgentCore browser (there is
# no local Chromium in this artifact).
_DEFAULT_OPTIONS: Dict[str, Any] = {
    "rendered": True,
    "agent": True,
    "browser_backend": "agentcore",
    "auto_fix": True,
}

# Prefix convention (see module docstring).
PDF_PREFIX = "pdf/"
HTML_PREFIX = "html/"
OUTPUT_PREFIX = "accessible/"
MANIFEST_NAME = "manifest.json"


@app.entrypoint
def invoke(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Route one uploaded object to the convert or audit stage."""
    input_bucket = payload.get("input_bucket")
    input_key = payload.get("input_key")
    if not input_bucket or not input_key:
        return {"status": "error", "error": "payload requires input_bucket and input_key"}

    output_bucket = payload.get("output_bucket") or input_bucket
    mode = payload.get("mode") or _infer_mode(input_key)

    options = dict(_DEFAULT_OPTIONS)
    options.update(payload.get("options") or {})
    options.setdefault(
        "agentcore_region",
        os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION"),
    )

    job_id = payload.get("job_id") or generate_job_id(input_bucket, input_key)
    logger.info("Pipeline start: mode=%s job=%s s3://%s/%s", mode, job_id, input_bucket, input_key)

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
            update_job_status(job_id, status=STATUS_FAILED, stage="PIPELINE", details={"error": str(e)})
        except Exception:  # pragma: no cover
            pass
        return {"status": "error", "job_id": job_id, "error": str(e)}


def _infer_mode(input_key: str) -> str:
    """Infer the pipeline mode from the object key prefix."""
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

        # Reuse the existing uploader (now directory-safe) to write the bundle
        # under html/<name>/.
        s3_results = upload_conversion_results(result, input_key, output_bucket)

        # Write the manifest LAST so the audit trigger sees a complete bundle.
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
        s3_client.put_object(
            Bucket=output_bucket,
            Key=manifest_key,
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
    update_job_status(job_id, STATUS_PROCESSING, STAGE_AUDIT, {"input_key": input_key})

    with tempfile.TemporaryDirectory() as tmp:
        work = os.path.join(tmp, "html")
        os.makedirs(work, exist_ok=True)

        # Materialize the input into a local directory and pick the audit target
        # (a single file or the directory for multi-page).
        audit_target, multi_page, name = _materialize_html_input(
            input_bucket, input_key, work
        )
        if multi_page:
            options = {**options, "multi_page": True}

        # Audit.
        audit_report = os.path.join(tmp, "audit.json")
        audit_result = audit_html_accessibility(
            html_path=audit_target, image_dir=work, options=options, output_path=audit_report
        )

        # Remediate (agent render -> fix -> verify) against the same target.
        remediated_out = os.path.join(tmp, "remediated")
        os.makedirs(remediated_out, exist_ok=True)
        remediate_html_accessibility(
            html_path=audit_target,
            audit_report=audit_result,
            output_path=remediated_out,
            image_dir=work,
            options=options,
        )

        # Publish every produced artifact under accessible/<name>/.
        out_prefix = f"{OUTPUT_PREFIX}{name}/"
        published = _publish_tree(remediated_out, output_bucket, out_prefix)

    update_job_status(
        job_id, STATUS_COMPLETED, STAGE_COMPLETE,
        {"output_prefix": out_prefix, "output_bucket": output_bucket, "files": len(published)},
    )
    logger.info("Audit+remediate complete: job=%s -> s3://%s/%s (%d files)",
                job_id, output_bucket, out_prefix, len(published))
    return {
        "status": "completed", "stage": "audit", "job_id": job_id,
        "output_bucket": output_bucket, "output_prefix": out_prefix,
        "published_keys": published,
        "total_issues": audit_result.get("summary", {}).get("total_issues"),
    }


def _materialize_html_input(
    bucket: str, key: str, work_dir: str
) -> Tuple[str, bool, str]:
    """Download the audit input into ``work_dir``; return (audit_target, multi_page, name).

    Handles the three accepted shapes:
      - manifest.json  -> download every file in the bundle; multi-page if >1 html.
      - .zip           -> extract HTML+CSS+JS; multi-page if >1 html.
      - single .html   -> download the one file.
    """
    fname = os.path.basename(key)

    if fname == MANIFEST_NAME:
        name = key[len(HTML_PREFIX):].rstrip("/").rsplit("/", 1)[0] if key.startswith(HTML_PREFIX) else "document"
        return _materialize_bundle(bucket, key, work_dir, name)

    if fname.lower().endswith(".zip"):
        name = os.path.splitext(fname)[0]
        local_zip = os.path.join(work_dir, fname)
        s3_client.download_file(bucket, key, local_zip)
        with zipfile.ZipFile(local_zip) as zf:
            _safe_extract_zip(zf, work_dir)
        os.remove(local_zip)
        return _pick_html_target(work_dir, name)

    # Single HTML file.
    name = os.path.splitext(fname)[0]
    local_html = os.path.join(work_dir, fname)
    s3_client.download_file(bucket, key, local_html)
    return local_html, False, name


def _materialize_bundle(bucket: str, manifest_key: str, work_dir: str, name: str) -> Tuple[str, bool, str]:
    """Download every object in a converted bundle described by its manifest."""
    obj = s3_client.get_object(Bucket=bucket, Key=manifest_key)
    manifest = json.loads(obj["Body"].read())
    bundle_prefix = manifest_key.rsplit("/", 1)[0] + "/"

    keys: List[str] = [manifest["html_key"]]
    keys += manifest.get("html_files", [])
    keys += manifest.get("image_files", [])
    keys += manifest.get("css_files", [])

    for k in keys:
        # Preserve the path relative to the bundle prefix so relative links
        # (images/, css/) resolve when rendered.
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
    """Extract a zip, rejecting entries that escape ``dest_dir`` (zip-slip).

    User-uploaded zips are untrusted, so each member's resolved path must stay
    within the destination directory.
    """
    dest_root = os.path.realpath(dest_dir)
    for member in zf.namelist():
        target = os.path.realpath(os.path.join(dest_dir, member))
        if target != dest_root and not target.startswith(dest_root + os.sep):
            raise ValueError(f"Unsafe path in zip (path traversal): {member}")
    zf.extractall(dest_dir)


def _pick_html_target(work_dir: str, name: str) -> Tuple[str, bool, str]:
    """After extracting a zip, choose the audit target and page mode."""
    html_files = []
    for root, _dirs, files in os.walk(work_dir):
        for f in files:
            if f.lower().endswith(".html"):
                html_files.append(os.path.join(root, f))
    if not html_files:
        raise ValueError("Zip contained no .html files to audit")
    if len(html_files) > 1:
        # Multiple pages: audit the directory. Prefer a top-level index/document
        # as the representative file but hand the auditor the directory.
        return work_dir, True, name
    return html_files[0], False, name


def _publish_tree(local_dir: str, bucket: str, out_prefix: str) -> List[str]:
    """Upload every file under ``local_dir`` to ``out_prefix``; return the keys."""
    published: List[str] = []
    for root, _dirs, files in os.walk(local_dir):
        for f in files:
            local_path = os.path.join(root, f)
            rel = os.path.relpath(local_path, local_dir)
            key = f"{out_prefix}{rel}".replace(os.sep, "/")
            s3_client.upload_file(local_path, bucket, key)
            published.append(key)
    return published


if __name__ == "__main__":
    app.run()
