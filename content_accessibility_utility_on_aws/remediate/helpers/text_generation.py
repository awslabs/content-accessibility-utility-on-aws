# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Model-backed short text generation for remediation strategies.

Several remediation strategies need to produce a short piece of human-facing
text (a heading, a document title, a form label, descriptive link text). This
module centralizes the Bedrock call and the cleanup of the result so each
strategy can request text the same way and degrade gracefully when no model
client is available.

The contract: ``generate_short_text`` returns ``None`` when no model is in use
(no client, e.g. ``--no-ai``) or there is no context to ground on, and callers
keep their rule-based behavior for that case. When a client *is* present and
the model call fails, it raises ``NeedsReviewError`` so the issue is left
unfixed and flagged for review, rather than silently replaced by generic
fallback text.
"""

import re
from typing import Optional

from content_accessibility_utility_on_aws.utils.logging_helper import (
    setup_logger,
    NeedsReviewError,
)

logger = setup_logger(__name__)


def strip_quotes_and_trailing_period(text: str) -> str:
    """
    Strip surrounding quotes and any trailing period(s) from generated text.

    Shared by ``clean_generated_text`` and the alt-text cleaner so both treat
    model-added quotes and sentence-ending periods the same way.
    """
    if not text:
        return ""
    return text.strip("\"'").rstrip(".")


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

    # Models occasionally prefix a label like "Heading:" or "Title -".
    text = re.sub(r"^(heading|title|label|link text)\s*[:\-]\s*", "", text, flags=re.IGNORECASE)

    # Collapse whitespace/newlines to a single line.
    text = " ".join(text.split())

    # Strip surrounding quotes and a trailing period (headings/labels are not
    # sentences); shared with the alt-text cleaner.
    text = strip_quotes_and_trailing_period(text)

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
        Cleaned text, or None if generation was skipped (no client or context).

    Raises:
        NeedsReviewError: If a client was given but the model call failed or
            returned nothing usable (``model_failed=True``).
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
    except Exception as e:  # noqa: BLE001 - any model error means "needs review"
        logger.warning(f"Model text generation failed for {purpose}: {e}")
        raise NeedsReviewError(
            f"Model call failed ({purpose}): {e}", model_failed=True
        ) from e

    cleaned = clean_generated_text(raw, max_words=max_words)
    if not cleaned:
        raise NeedsReviewError(
            f"Model returned no usable text ({purpose})", model_failed=True
        )
    return cleaned
