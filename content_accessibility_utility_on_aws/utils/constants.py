# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Shared constants for the content accessibility utility.

Centralizes the default Bedrock model id so it is defined in exactly one place.
Changing the default model only requires editing this file.
"""

# Default Bedrock model used for remediation and alt-text generation.
#
# Uses the Amazon Nova 2 Lite cross-region inference profile ("us." prefix).
# Nova 2 Lite is a fast, low-cost multimodal model well suited to the
# high-volume document remediation and image alt-text workloads in this tool.
# It is invoked through the model-agnostic Bedrock Converse API, so any other
# Converse-compatible model id (e.g. "us.anthropic.claude-haiku-4-5-20251001-v1:0")
# can be substituted via --model-id or configuration.
DEFAULT_MODEL_ID = "us.amazon.nova-2-lite-v1:0"

# Default maximum tokens to request from the model when generating text. The
# previous value of 500 truncated verbose remediation output; 2000 gives the
# model enough room for table analysis and detailed alt text.
DEFAULT_MAX_TOKENS = 2000

# Deterministic generation by default. Accessibility remediation favors
# repeatable, structured output over creative variation.
DEFAULT_TEMPERATURE = 0.0
