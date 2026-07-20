# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Shared constants for the content accessibility utility.

Centralizes the default Bedrock model id so it is defined in exactly one place.
Changing the default model only requires editing this file.
"""

# Default Bedrock model used for remediation and alt-text generation.
#
# Uses the Claude Sonnet 5 cross-region inference profile ("us." prefix). Sonnet
# 5 is a strong multimodal model chosen for the semantic-authoring quality that
# remediation depends on — accessible names for custom widgets, descriptive link
# text, and image alt text — where a weaker/cheaper model produced generic or
# duplicate output. It is invoked through the model-agnostic Bedrock Converse
# API, so any other Converse-compatible model id (e.g. a faster, lower-cost
# "us.amazon.nova-2-lite-v1:0" for high-volume batch runs) can be substituted
# via --model-id or configuration.
DEFAULT_MODEL_ID = "us.anthropic.claude-sonnet-5"

# Default maximum tokens to request from the model when generating text. The
# previous value of 500 truncated verbose remediation output; 2000 gives the
# model enough room for table analysis and detailed alt text.
DEFAULT_MAX_TOKENS = 2000

# Deterministic generation by default. Accessibility remediation favors
# repeatable, structured output over creative variation.
DEFAULT_TEMPERATURE = 0.0

# Some newer Bedrock models (e.g. the Claude Sonnet 5 family) reject the
# `temperature` inference parameter with a ValidationException
# ("temperature is deprecated for this model"), while older ones (e.g. Nova)
# still require/accept it. Model ids matching any of these prefixes must have
# `temperature` omitted from Converse / BedrockModel calls. Keep this list in
# one place so every call site stays consistent.
_TEMPERATURE_UNSUPPORTED_PREFIXES = (
    "us.anthropic.claude-sonnet-5",
    "anthropic.claude-sonnet-5",
    "us.anthropic.claude-opus-4",
    "anthropic.claude-opus-4",
)


def model_supports_temperature(model_id: str) -> bool:
    """Return False for models known to reject the `temperature` parameter."""
    mid = (model_id or "").lower()
    return not any(mid.startswith(p) for p in _TEMPERATURE_UNSUPPORTED_PREFIXES)


# WCAG 2.2 Success Criterion 2.5.8 minimum interactive target size, in CSS
# pixels. Shared by the audit check and the remediation strategy so the size
# they detect against and enforce to cannot drift apart.
MIN_TARGET_SIZE_PX = 24

