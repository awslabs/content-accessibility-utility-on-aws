# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
S3-triggered Lambda that hands each uploaded document to the AgentCore Runtime.

This is intentionally thin: it does no accessibility work itself. When a PDF
lands in the input bucket, S3 invokes this function; it parses the event and
calls ``bedrock-agentcore:InvokeAgentRuntime`` with a small JSON payload telling
the runtime where the input is and where to write output. All the heavy lifting
(convert → audit → agent-remediate, and the managed browser) happens in the
runtime, which can run far longer than Lambda's 15-minute limit.

Environment:
    AGENT_RUNTIME_ARN  ARN of the deployed AgentCore Runtime to invoke (required).
    OUTPUT_BUCKET      Bucket to write results to (defaults to the input bucket).
    OUTPUT_PREFIX      Prefix for results (default "accessible/").
"""

import json
import os
import uuid

import boto3

_agentcore = boto3.client("bedrock-agentcore")

_RUNTIME_ARN = os.environ.get("AGENT_RUNTIME_ARN")
_OUTPUT_BUCKET = os.environ.get("OUTPUT_BUCKET")
_OUTPUT_PREFIX = os.environ.get("OUTPUT_PREFIX", "accessible/")

# Only trigger on PDFs; other uploads (including our own HTML output) are ignored
# so the pipeline does not recurse when input and output share a bucket.
_TRIGGER_SUFFIXES = (".pdf",)


def _s3_records(event):
    """Yield (bucket, key) for each S3 object-created record in the event."""
    for record in event.get("Records", []):
        if record.get("eventSource") != "aws:s3":
            continue
        s3 = record.get("s3", {})
        bucket = s3.get("bucket", {}).get("name")
        key = s3.get("object", {}).get("key")
        if bucket and key:
            # S3 event keys are URL-encoded (spaces -> '+', etc.).
            from urllib.parse import unquote_plus

            yield bucket, unquote_plus(key)


def handler(event, context):
    """Invoke the AgentCore Runtime once per uploaded PDF."""
    if not _RUNTIME_ARN:
        raise RuntimeError("AGENT_RUNTIME_ARN environment variable is not set")

    invoked = []
    for bucket, key in _s3_records(event):
        if not key.lower().endswith(_TRIGGER_SUFFIXES):
            print(f"Skipping non-PDF object: s3://{bucket}/{key}")
            continue

        payload = {
            "input_bucket": bucket,
            "input_key": key,
            "output_bucket": _OUTPUT_BUCKET or bucket,
            "output_prefix": _OUTPUT_PREFIX,
        }

        # A stable-ish session id per object keeps the invocation traceable.
        session_id = f"a11y-{uuid.uuid4().hex}"
        print(f"Invoking runtime for s3://{bucket}/{key} (session {session_id})")

        _agentcore.invoke_agent_runtime(
            agentRuntimeArn=_RUNTIME_ARN,
            runtimeSessionId=session_id,
            payload=json.dumps(payload).encode("utf-8"),
        )
        invoked.append({"bucket": bucket, "key": key, "session_id": session_id})

    return {"invoked": invoked, "count": len(invoked)}
