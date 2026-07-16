# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
AgentCore Runtime entrypoint for the managed accessibility pipeline.

This module is what Amazon Bedrock AgentCore Runtime hosts. When a PDF is
uploaded to the input S3 bucket, a trigger Lambda invokes this runtime with a
JSON payload describing the object; the entrypoint runs the full pipeline —
convert (PDF→HTML via BDA) → audit → **agent** remediation (render → fix →
verify in a browser) — and writes every artifact to the output S3 location.

Why this runs on AgentCore Runtime rather than Lambda:
  - The pipeline (BDA conversion + multi-page rendered remediation) can exceed
    Lambda's 15-minute ceiling; Runtime supports long sessions.
  - The rendered layer uses the managed AgentCore **Browser Tool** via
    ``AgentCoreBrowserProbe`` (no Chromium in this artifact); running the agent
    next to that service keeps the browser call in-region and same-credential.

The payload contract (kept deliberately small):

    {
      "input_bucket":  "<bucket with the uploaded PDF>",
      "input_key":     "<key of the uploaded PDF>",
      "output_bucket": "<bucket to write results to>",   # optional; defaults to input_bucket
      "output_prefix": "<prefix under which results go>", # optional; default "accessible/"
      "options":       { ... }                            # optional pipeline options
    }

It reuses the existing batch stage processors and job-status helpers so the
pipeline logic and DynamoDB tracking are not duplicated here.
"""

from __future__ import annotations

import os
from typing import Any, Dict

from bedrock_agentcore.runtime import BedrockAgentCoreApp

from content_accessibility_utility_on_aws.batch import audit as batch_audit
from content_accessibility_utility_on_aws.batch import pdf2html as batch_pdf2html
from content_accessibility_utility_on_aws.batch import remediate as batch_remediate
from content_accessibility_utility_on_aws.batch.common import (
    STAGE_COMPLETE,
    STATUS_FAILED,
    create_job_record,
    generate_job_id,
    update_job_status,
)
from content_accessibility_utility_on_aws.utils.logging_helper import setup_logger

logger = setup_logger(__name__)

app = BedrockAgentCoreApp()

# The rendered/agent layer must target the managed AgentCore browser (not a
# local Chromium, which is not present in this artifact). Force that backend for
# every pipeline run hosted here.
_DEFAULT_OPTIONS: Dict[str, Any] = {
    "rendered": True,
    "agent": True,
    "browser_backend": "agentcore",
    "auto_fix": True,
}

_DEFAULT_OUTPUT_PREFIX = "accessible/"


@app.entrypoint
def invoke(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Run the accessibility pipeline for one uploaded document.

    Returns a JSON-serializable summary of every stage plus the job id. Raising
    would mark the runtime invocation failed; instead we record FAILED status on
    the job and return a structured error so the trigger has an audit trail.
    """
    input_bucket = payload.get("input_bucket")
    input_key = payload.get("input_key")
    if not input_bucket or not input_key:
        return {"status": "error", "error": "payload requires input_bucket and input_key"}

    output_bucket = payload.get("output_bucket") or input_bucket
    output_prefix = (payload.get("output_prefix") or _DEFAULT_OUTPUT_PREFIX).rstrip("/") + "/"

    # Merge caller options over the hosted defaults (agentcore browser + agent).
    options = dict(_DEFAULT_OPTIONS)
    options.update(payload.get("options") or {})
    # Region for the managed browser: inherit the runtime's region.
    options.setdefault(
        "agentcore_region",
        os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION"),
    )

    job_id = payload.get("job_id") or generate_job_id(input_bucket, input_key)
    logger.info("Pipeline start: job=%s s3://%s/%s", job_id, input_bucket, input_key)

    try:
        create_job_record(job_id, document_key=input_key)

        # Stage 1: PDF -> HTML (Bedrock Data Automation).
        conversion = batch_pdf2html.process_pdf_document(
            job_id=job_id,
            source_bucket=input_bucket,
            source_key=input_key,
            destination_bucket=output_bucket,
            options=options,
        )
        html_key = conversion["html_key"]

        # Stage 2: accessibility audit (static + rendered, because options set
        # rendered=True) of the produced HTML.
        audit = batch_audit.process_html_document(
            job_id=job_id,
            source_bucket=output_bucket,
            source_key=html_key,
            destination_bucket=output_bucket,
            options=options,
        )

        # Stage 3: remediation. With agent options set, the remediation manager
        # applies interactive fixes and the rendered layer verifies them.
        remediation = batch_remediate.process_html_with_audit(
            job_id=job_id,
            html_bucket=output_bucket,
            html_key=html_key,
            audit_bucket=output_bucket,
            audit_key=audit["audit_key"],
            destination_bucket=output_bucket,
            options=options,
        )

        # Copy the final remediated HTML to the requested output prefix so
        # consumers have one predictable location to read from.
        final_key = _publish_result(
            output_bucket, remediation["remediated_key"], output_prefix, input_key
        )

        update_job_status(
            job_id,
            status="COMPLETED",
            stage=STAGE_COMPLETE,
            details={"output_key": final_key, "output_bucket": output_bucket},
        )
        logger.info("Pipeline complete: job=%s -> s3://%s/%s", job_id, output_bucket, final_key)

        return {
            "status": "completed",
            "job_id": job_id,
            "output_bucket": output_bucket,
            "output_key": final_key,
            "html_key": html_key,
            "audit_key": audit["audit_key"],
            "remediated_key": remediation["remediated_key"],
            "issues_remediated": remediation.get("issues_remediated"),
        }

    except Exception as e:  # keep the runtime invocation itself successful
        logger.exception("Pipeline failed: job=%s", job_id)
        try:
            update_job_status(
                job_id, status=STATUS_FAILED, stage="PIPELINE", details={"error": str(e)}
            )
        except Exception:  # pragma: no cover - status write is best effort
            pass
        return {"status": "error", "job_id": job_id, "error": str(e)}


def _publish_result(bucket: str, remediated_key: str, output_prefix: str, input_key: str) -> str:
    """Copy the remediated HTML to the caller's output prefix; return its key.

    Uses a server-side S3 copy (no download) via the shared client so the final
    artifact lives at a predictable ``{output_prefix}{original_name}.html``.
    """
    import os as _os

    from content_accessibility_utility_on_aws.batch.common import s3_client

    base = _os.path.splitext(_os.path.basename(input_key))[0]
    final_key = f"{output_prefix}{base}.html"
    s3_client.copy_object(
        Bucket=bucket,
        Key=final_key,
        CopySource={"Bucket": bucket, "Key": remediated_key},
    )
    return final_key


if __name__ == "__main__":
    # Local dev server (AgentCore Runtime calls the same entrypoint).
    app.run()
