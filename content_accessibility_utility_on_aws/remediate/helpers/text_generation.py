# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Model-backed short text generation for remediation strategies.

Several remediation strategies need to produce a short piece of human-facing
text (a heading, a document title, a form label, descriptive link text). This
module centralizes the Bedrock call and the cleanup of the result so each
strategy can request text the same way and degrade gracefully when no model
client is available.

The contract is intentionally fallback-first: ``generate_short_text`` returns
``None`` whenever a model result cannot be produced (no client, empty context,
or an API error), and callers keep their existing rule-based behavior for that
case. This means enabling the model improves output quality without changing
the behavior of runs that have no Bedrock access.
"""

import re
from typing import Optional

from content_accessibility_utility_on_aws.utils.logging_helper import setup_logger

logger = setup_logger(__name__)


def clean_generated_text(text: str, max_words: Optional[int] = None) -> str:
    """
    Normalize a model-generated short text snippet.

    Strips surrounding quotes/markup fences, collapses whitespace, removes a
    trailing period, and optionally truncates to a word budget.

    Args:
        text: The raw model output.
        max_words: Optional maximum number of words to keep.

    Returns:
        Cleaned single-line text (may be empty).
    """
    if not text:
        return ""

    # Drop code fences and surrounding quotes the model sometimes adds.
    text = text.strip()
    text = re.sub(r"^```[a-zA-Z]*\n?|```$", "", text).strip()
    text = text.strip("\"'")

    # Models occasionally prefix a label like "Heading:" or "Title -".
    text = re.sub(r"^(heading|title|label|link text)\s*[:\-]\s*", "", text, flags=re.IGNORECASE)

    # Collapse whitespace/newlines to a single line.
    text = " ".join(text.split())

    # Remove a single trailing period (headings/labels are not sentences).
    text = text.rstrip(".")

    if max_words is not None:
        words = text.split()
        if len(words) > max_words:
            text = " ".join(words[:max_words])

    return text.strip()


def generate_short_text(
    bedrock_client,
    instruction: str,
    context: str,
    *,
    purpose: str,
    max_words: Optional[int] = None,
    max_tokens: int = 60,
) -> Optional[str]:
    """
    Generate a short text snippet with the model, or None if unavailable.

    Args:
        bedrock_client: A BedrockClient, or None. When None, returns None so the
            caller can fall back to its rule-based behavior.
        instruction: What to produce (e.g. "Write a concise, descriptive
            heading for the section below.").
        context: The surrounding document text the model should base the
            output on. If empty/whitespace, returns None (nothing to ground on).
        purpose: Usage-tracking label passed through to the model call.
        max_words: Optional word budget enforced during cleanup.
        max_tokens: Token ceiling for the model response.

    Returns:
        Cleaned text, or None if generation was skipped or failed.
    """
    if bedrock_client is None:
        return None

    if not context or not context.strip():
        return None

    prompt = (
        f"{instruction}\n\n"
        "Respond with only the text itself — no quotes, labels, or explanation.\n\n"
        f"Context:\n{context.strip()}"
    )

    try:
        raw = bedrock_client.generate_text(
            prompt, purpose=purpose, max_tokens=max_tokens
        )
    except Exception as e:  # pragma: no cover - defensive; model errors are non-fatal
        logger.warning(f"Model text generation failed for {purpose}: {e}")
        return None

    cleaned = clean_generated_text(raw, max_words=max_words)
    return cleaned or None
