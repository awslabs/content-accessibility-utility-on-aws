# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Phase 4 — generated-text cleanup unit tests.
"""

from content_accessibility_utility_on_aws.remediate.helpers.text_generation import (
    clean_generated_text,
    strip_quotes_and_trailing_period,
    generate_short_text,
)


def test_strip_quotes_and_trailing_period():
    assert strip_quotes_and_trailing_period('"Hello."') == "Hello"
    assert strip_quotes_and_trailing_period("'World'") == "World"
    assert strip_quotes_and_trailing_period("") == ""


def test_clean_strips_code_fences_and_quotes():
    assert clean_generated_text('```\n"Quarterly Results"\n```') == "Quarterly Results"


def test_clean_strips_label_prefix():
    assert clean_generated_text("Heading: Cost Savings") == "Cost Savings"
    assert clean_generated_text("Title - Annual Report") == "Annual Report"


def test_clean_collapses_whitespace():
    assert clean_generated_text("Multi   line\n  text") == "Multi line text"


def test_clean_truncates_to_max_words():
    assert clean_generated_text("one two three four five", max_words=3) == "one two three"


def test_clean_empty_returns_empty():
    assert clean_generated_text("") == ""


def test_generate_short_text_returns_none_without_client():
    # Fallback-first contract: no client -> None so the caller uses rules.
    assert generate_short_text(None, instruction="x", context="some context", purpose="p") is None


def test_generate_short_text_returns_none_without_context():
    class _Client:
        def generate_text(self, *a, **k):
            return "should not be called"

    assert generate_short_text(_Client(), instruction="x", context="", purpose="p") is None


def test_generate_short_text_uses_client_output():
    class _Client:
        def generate_text(self, prompt, purpose="general", max_tokens=2000, **k):
            return "Cost Savings Summary"

    result = generate_short_text(
        _Client(), instruction="Write a heading", context="some section text", purpose="heading"
    )
    assert result == "Cost Savings Summary"
