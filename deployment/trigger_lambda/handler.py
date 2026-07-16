# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
S3-triggered Lambda that routes uploads to the AgentCore Runtime pipeline.

Prefix-based routing (see the runtime entrypoint for the full contract):

    pdf/<name>.pdf                 -> mode "convert"  (PDF -> HTML bundle)
    html/<name>.html               -> mode "audit"    (single HTML file)
    html/<name>.zip                -> mode "audit"    (HTML+CSS+JS bundle)
    html/<name>/manifest.json      -> mode "audit"    (converted multi-file bundle)

Crucially, the converted bundle emits many objects (document.html, images/,
css/). Each fires its own S3 event, but audit must run ONCE per document with
all assets present. So this Lambda triggers audit only on the manifest.json
marker (written last by the convert stage) and IGNORES every other object under
a bundle directory. That is the multi-file, event-driven safety mechanism.

Environment:
    AGENT_RUNTIME_ARN  ARN of the deployed AgentCore Runtime (required).
    OUTPUT_BUCKET      Bucket to write results to (defaults to the input bucket).
"""

import json
import os
import uuid
from urllib.parse import unquote_plus

import boto3

_agentcore = boto3.client("bedrock-agentcore")

_RUNTIME_ARN = os.environ.get("AGENT_RUNTIME_ARN")
_OUTPUT_BUCKET = os.environ.get("OUTPUT_BUCKET")

PDF_PREFIX = "pdf/"
HTML_PREFIX = "html/"
MANIFEST_NAME = "manifest.json"


def _s3_records(event):
    for record in event.get("Records", []):
        if record.get("eventSource") != "aws:s3":
            continue
        s3 = record.get("s3", {})
        bucket = s3.get("bucket", {}).get("name")
        key = s3.get("object", {}).get("key")
        if bucket and key:
            yield bucket, unquote_plus(key)


def _route(key):
    """Return (mode, reason) for a key, or (None, reason) to skip it.

    Skipping is as important as routing: the convert stage's own asset objects
    under html/<name>/ must NOT each trigger an audit — only their manifest does.
    """
    lower = key.lower()

    if key.startswith(PDF_PREFIX):
        if lower.endswith(".pdf"):
            return "convert", "pdf upload"
        return None, "non-pdf under pdf/"

    if key.startswith(HTML_PREFIX):
        rest = key[len(HTML_PREFIX):]
        depth = rest.count("/")

        # Converted bundle: html/<name>/...  -> only the manifest triggers audit.
        if depth >= 1:
            if os.path.basename(key) == MANIFEST_NAME:
                return "audit", "bundle manifest"
            return None, "bundle asset (awaiting manifest)"

        # Top-level html/<file>: a directly uploaded single HTML or a zip.
        if lower.endswith(".html") or lower.endswith(".htm"):
            return "audit", "single html upload"
        if lower.endswith(".zip"):
            return "audit", "zip upload"
        return None, "unsupported html/ object"

    return None, "outside pdf/ and html/ prefixes"


def handler(event, context):
    if not _RUNTIME_ARN:
        raise RuntimeError("AGENT_RUNTIME_ARN environment variable is not set")

    invoked = []
    for bucket, key in _s3_records(event):
        mode, reason = _route(key)
        if mode is None:
            print(f"Skip s3://{bucket}/{key} ({reason})")
            continue

        payload = {
            "mode": mode,
            "input_bucket": bucket,
            "input_key": key,
            "output_bucket": _OUTPUT_BUCKET or bucket,
        }
        session_id = f"a11y-{uuid.uuid4().hex}"
        print(f"Route s3://{bucket}/{key} -> {mode} ({reason}); session {session_id}")

        _agentcore.invoke_agent_runtime(
            agentRuntimeArn=_RUNTIME_ARN,
            runtimeSessionId=session_id,
            payload=json.dumps(payload).encode("utf-8"),
        )
        invoked.append({"key": key, "mode": mode, "session_id": session_id})

    return {"invoked": invoked, "count": len(invoked)}
