# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Tests for the model-agnostic `temperature` handling in BedrockClient.

Newer models (e.g. Claude Sonnet 5) reject the `temperature` inference
parameter with a ValidationException, while older ones (e.g. Nova) accept it.
The client sends `temperature` optimistically and, on the first rejection,
drops it and retries — then omits it for the rest of the client's life. These
tests exercise that fallback without any network calls by stubbing the
underlying boto3 converse method.
"""

from unittest.mock import MagicMock, patch

import pytest

from content_accessibility_utility_on_aws.remediate.services.bedrock_client import (
    BedrockClient,
)
from content_accessibility_utility_on_aws.utils.constants import (
    model_supports_temperature,
)


def _ok_response(text: str = "hello") -> dict:
    return {
        "output": {"message": {"role": "assistant", "content": [{"text": text}]}},
        "stopReason": "end_turn",
        "usage": {"inputTokens": 5, "outputTokens": 2},
    }


def _make_client(model_id: str = "some.unknown-future-model-v9") -> BedrockClient:
    # Patch the session so __init__ does not touch AWS. Default to an UNKNOWN
    # model id so `_supports_temperature` starts True and the reactive-retry
    # fallback path is exercised; known temperature-less models (sonnet-5) start
    # False proactively and are covered separately.
    with patch(
        "content_accessibility_utility_on_aws.remediate.services.bedrock_client.boto3"
    ) as boto3_mock:
        boto3_mock.Session.return_value.client.return_value = MagicMock()
        client = BedrockClient(model_id=model_id)
    return client


class _TemperatureError(Exception):
    """Mimics botocore ValidationException for a deprecated temperature."""


def test_retries_without_temperature_on_rejection():
    client = _make_client()
    converse = client.client.converse
    # First call rejects temperature, second (retry) succeeds.
    converse.side_effect = [
        _TemperatureError(
            "An error occurred (ValidationException) when calling the Converse "
            "operation: The model returned the following errors: `temperature` "
            "is deprecated for this model."
        ),
        _ok_response("fixed"),
    ]

    result = client.generate_text("prompt", purpose="test")

    assert result == "fixed"
    assert converse.call_count == 2
    # Retry must have dropped temperature.
    retry_cfg = converse.call_args_list[1].kwargs["inferenceConfig"]
    assert "temperature" not in retry_cfg
    # And the client remembers so it won't send it again.
    assert client._supports_temperature is False


def test_omits_temperature_on_subsequent_calls():
    client = _make_client()
    converse = client.client.converse
    converse.side_effect = [
        _TemperatureError("`temperature` is deprecated for this model"),
        _ok_response(),
        _ok_response(),
    ]

    client.generate_text("first", purpose="test")
    converse.reset_mock(side_effect=False)
    converse.return_value = _ok_response("second")

    client.generate_text("second", purpose="test")

    # The second top-level call must not include temperature at all (no retry).
    assert converse.call_count == 1
    cfg = converse.call_args.kwargs["inferenceConfig"]
    assert "temperature" not in cfg


def test_non_temperature_error_propagates():
    client = _make_client()
    client.client.converse.side_effect = RuntimeError("throttled")

    from content_accessibility_utility_on_aws.remediate.services.bedrock_client import (
        AltTextGenerationError,
    )

    with pytest.raises(AltTextGenerationError):
        client.generate_text("prompt", purpose="test")
    # A single attempt — no spurious retry for unrelated errors.
    assert client.client.converse.call_count == 1
    assert client._supports_temperature is True


def test_known_temperatureless_model_never_sends_temperature():
    # Sonnet 5 is known up front, so the FIRST call must already omit
    # temperature — no failed round-trip, no reliance on the reactive retry.
    # This is the race fix: many short-lived clients each making one rapid call
    # would otherwise each send temperature and fail before any learned to stop.
    client = _make_client(model_id="us.anthropic.claude-sonnet-5")
    assert client._supports_temperature is False
    client.client.converse.return_value = _ok_response("ok")

    client.generate_text("prompt", purpose="test")

    assert client.client.converse.call_count == 1  # no retry needed
    cfg = client.client.converse.call_args.kwargs["inferenceConfig"]
    assert "temperature" not in cfg


def test_known_temperatured_model_sends_temperature():
    client = _make_client(model_id="us.amazon.nova-2-lite-v1:0")
    assert client._supports_temperature is True
    client.client.converse.return_value = _ok_response("ok")

    client.generate_text("prompt", purpose="test")

    cfg = client.client.converse.call_args.kwargs["inferenceConfig"]
    assert "temperature" in cfg


@pytest.mark.parametrize(
    "model_id,expected",
    [
        ("us.anthropic.claude-sonnet-5", False),
        ("anthropic.claude-sonnet-5", False),
        ("us.amazon.nova-2-lite-v1:0", True),
        ("us.anthropic.claude-3-5-sonnet-20241022-v2:0", True),
    ],
)
def test_model_supports_temperature(model_id, expected):
    assert model_supports_temperature(model_id) is expected
