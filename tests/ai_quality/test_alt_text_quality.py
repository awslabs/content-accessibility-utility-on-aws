# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Phase 9 — AI quality suite for multimodal alt-text generation.

Runs the REAL multimodal Bedrock call against committed test images and judges
whether the generated alt text accurately and concisely describes each image.
This is the surface that most needs real evaluation: there is no way to know the
alt text is actually good without running the model and inspecting the result.
"""

import os

import pytest

from content_accessibility_utility_on_aws.remediate.prompt_generators.alt_text_generator import (
    generate_alt_text_prompt,
    clean_alt_text,
)

pytestmark = [pytest.mark.aws, pytest.mark.llm_judge]

FIXTURES = os.path.join(os.path.dirname(__file__), "..", "fixtures", "images")


def _gen_alt(bedrock_client, image_name, context=None):
    img_path = os.path.join(FIXTURES, image_name)
    assert os.path.exists(img_path), f"missing fixture {img_path}"
    prompt = generate_alt_text_prompt(img_path, context)
    raw = bedrock_client.generate_alt_text_for_image(img_path, prompt)
    return clean_alt_text(raw)


def test_bar_chart_alt_text_quality(bedrock_client, judge):
    alt = _gen_alt(
        bedrock_client,
        "bar_chart.png",
        context={"surrounding_text": "Our quarterly sales results for the year."},
    )
    assert alt, "no alt text generated"
    verdict = judge(
        alt,
        criteria=(
            "Good alt text for this image accurately identifies it as a bar chart "
            "of quarterly sales showing an increasing trend across Q1-Q4. It "
            "should be concise (ideally under ~125 characters), must not start "
            "with 'image of'/'picture of', and must not hallucinate data not "
            "shown. Reasonable description of the upward trend passes."
        ),
        context="A bar chart titled 'Quarterly Sales' with four bars (Q1-Q4) rising left to right.",
    )
    assert verdict.passed, f"Alt text quality below threshold:\n{verdict.explain()}\nAlt: {alt!r}"


def test_icon_alt_text_quality(bedrock_client, judge):
    alt = _gen_alt(bedrock_client, "stop_sign.png")
    assert alt, "no alt text generated"
    verdict = judge(
        alt,
        criteria=(
            "Good alt text identifies this as a red octagonal stop sign (or stop "
            "symbol). It should be concise and must not begin with 'image of'. "
            "Mentioning the word 'stop' and the sign/octagon shape passes."
        ),
        context="A red octagonal STOP sign icon.",
    )
    assert verdict.passed, f"Alt text quality below threshold:\n{verdict.explain()}\nAlt: {alt!r}"
