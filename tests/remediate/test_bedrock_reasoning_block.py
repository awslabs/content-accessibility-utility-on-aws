# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Tests for BedrockClient text extraction when the model returns a reasoning
block before the text block.

Reasoning-capable models (e.g. Claude Sonnet 5) may prepend a
``reasoningContent`` block to the Converse response, so the text is not at
``content[0]``. The client must scan for the text block rather than blindly
indexing position 0 (which raised ``KeyError: 'text'`` and broke translation
and remediation against Sonnet 5). Exercised without network calls by stubbing
the underlying boto3 converse method.
"""

from unittest.mock import MagicMock, patch

import pytest

from content_accessibility_utility_on_aws.remediate.services.bedrock_client import (
    BedrockClient,
    AltTextGenerationError,
)


def _make_client(model_id: str = "us.anthropic.claude-sonnet-5") -> BedrockClient:
    with patch(
        "content_accessibility_utility_on_aws.remediate.services.bedrock_client.boto3"
    ) as boto3_mock:
        boto3_mock.Session.return_value.client.return_value = MagicMock()
        return BedrockClient(model_id=model_id)


def _reasoning_then_text(text: str) -> dict:
    return {
        "output": {
            "message": {
                "role": "assistant",
                "content": [
                    {"reasoningContent": {"reasoningText": {"text": "", "signature": "x"}}},
                    {"text": text},
                ],
            }
        },
        "stopReason": "end_turn",
        "usage": {"inputTokens": 10, "outputTokens": 4},
    }


def test_generate_text_skips_leading_reasoning_block():
    client = _make_client()
    client.client.converse = MagicMock(return_value=_reasoning_then_text('["hola"]'))
    result = client.generate_text("translate this", purpose="content_translation")
    assert result == '["hola"]'


def test_generate_text_still_works_without_reasoning_block():
    client = _make_client()
    client.client.converse = MagicMock(
        return_value={
            "output": {"message": {"content": [{"text": "plain"}]}},
            "stopReason": "end_turn",
            "usage": {},
        }
    )
    assert client.generate_text("x") == "plain"


def test_generate_text_raises_when_only_reasoning_block():
    # A truncated response with no text block at all must raise, not KeyError.
    client = _make_client()
    client.client.converse = MagicMock(
        return_value={
            "output": {
                "message": {
                    "content": [
                        {"reasoningContent": {"reasoningText": {"text": ""}}}
                    ]
                }
            },
            "stopReason": "max_tokens",
            "usage": {},
        }
    )
    with pytest.raises(AltTextGenerationError):
        client.generate_text("x")


def test_extract_text_helper_scans_blocks():
    assert (
        BedrockClient._extract_text(_reasoning_then_text("found")) == "found"
    )
    assert BedrockClient._extract_text({"output": {"message": {"content": []}}}) is None
