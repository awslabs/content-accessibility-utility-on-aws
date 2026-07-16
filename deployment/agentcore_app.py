# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
AgentCore Runtime entrypoint for the managed accessibility pipeline.

Thin wrapper: Amazon Bedrock AgentCore Runtime hosts this module and calls the
``@app.entrypoint`` on each invocation. All pipeline logic lives in the
installed package (``content_accessibility_utility_on_aws.agent.pipeline``) so
this entrypoint and the bundled ``init-pipeline`` copy cannot drift.

The pipeline is prefix-routed on the S3 key:
    pdf/<name>.pdf            -> convert (PDF -> HTML bundle) + manifest.json
    html/<name>.html | .zip   -> audit + agent-remediate
    html/<name>/manifest.json -> audit + agent-remediate (converted bundle)

Payload contract:
    {
      "mode":          "convert" | "audit",   # optional; inferred from input_key
      "input_bucket":  "...",
      "input_key":     "...",
      "output_bucket": "...",                  # optional; defaults to input_bucket
      "options":       { ... },                # optional pipeline options
      "force":         false                   # optional; bypass idempotency skip
    }
"""

from typing import Any, Dict

from bedrock_agentcore.runtime import BedrockAgentCoreApp

from content_accessibility_utility_on_aws.agent.pipeline import run_pipeline

app = BedrockAgentCoreApp()


@app.entrypoint
def invoke(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Route one uploaded object through the accessibility pipeline."""
    return run_pipeline(payload)


if __name__ == "__main__":
    app.run()
