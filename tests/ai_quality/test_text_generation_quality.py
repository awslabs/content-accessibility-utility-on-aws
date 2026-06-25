# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Phase 9 — AI quality suites for the text-generation surfaces.

Each test runs a REAL Bedrock generation through the shared helper and judges
the output against a WCAG-grounded rubric. Marked aws + llm_judge so it only
runs in the opt-in tier.
"""

import pytest

from content_accessibility_utility_on_aws.remediate.helpers.text_generation import (
    generate_short_text,
)

pytestmark = [pytest.mark.aws, pytest.mark.llm_judge]


def test_heading_generation_quality(bedrock_client, judge):
    section_text = (
        "The company reduced operating costs by 12 percent this year through "
        "warehouse automation and renegotiated supplier contracts, improving "
        "gross margins across all regions."
    )
    output = generate_short_text(
        bedrock_client,
        instruction=(
            "Write a concise, descriptive level-2 section heading (3-8 words) "
            "that summarizes the section text below."
        ),
        context=section_text,
        purpose="heading_generation",
        max_words=8,
    )
    assert output, "model returned no heading"
    verdict = judge(
        output,
        criteria=(
            "A good section heading is concise (3-8 words), accurately summarizes "
            "the section topic (cost reduction / margin improvement), is not "
            "generic (not 'Section 1'), and reads as a heading not a sentence."
        ),
        context=section_text,
    )
    assert verdict.passed, f"Heading quality below threshold:\n{verdict.explain()}"


def test_document_title_generation_quality(bedrock_client, judge):
    doc_text = (
        "This report covers the 2024 fiscal year financial performance of the "
        "organization, including revenue, operating costs, and the outlook for "
        "the next year."
    )
    output = generate_short_text(
        bedrock_client,
        instruction=(
            "Write a concise, descriptive page title (3-10 words) for the "
            "document whose text content is provided."
        ),
        context=doc_text,
        purpose="document_title_generation",
        max_words=12,
    )
    assert output, "model returned no title"
    verdict = judge(
        output,
        criteria=(
            "A good page title concisely describes the document's subject "
            "(2024 fiscal year financial report/performance), is specific rather "
            "than generic ('Document Title' would fail), and is reasonably short."
        ),
        context=doc_text,
    )
    assert verdict.passed, f"Title quality below threshold:\n{verdict.explain()}"


def test_form_label_generation_quality(bedrock_client, judge):
    context = (
        "Form control attributes: name=email type=email\n"
        "Nearby text: Enter your email address to subscribe to our newsletter"
    )
    output = generate_short_text(
        bedrock_client,
        instruction=(
            "Write a short form field label (1-4 words) for the form control "
            "described below, based on its attributes and nearby text."
        ),
        context=context,
        purpose="form_label_generation",
        max_words=4,
    )
    assert output, "model returned no label"
    verdict = judge(
        output,
        criteria=(
            "A good form label is short (1-4 words) and clearly names what the "
            "field collects (an email address). It must not be generic like "
            "'Label' or 'Input'."
        ),
        context=context,
    )
    assert verdict.passed, f"Label quality below threshold:\n{verdict.explain()}"


def test_link_text_generation_quality(bedrock_client, judge):
    context = (
        "Generic link text: 'click here'\n"
        "Surrounding text: Review our latest 10-K filing for full financial "
        "details. click here"
    )
    output = generate_short_text(
        bedrock_client,
        instruction=(
            "Rewrite the generic link text into descriptive link text (2-6 words) "
            "that states where the link goes. Do not use phrases like 'click "
            "here'. The link points to: https://example.com/filings/10-K-2024.pdf"
        ),
        context=context,
        purpose="link_text_generation",
        max_words=8,
    )
    assert output, "model returned no link text"
    lowered = output.lower()
    # Hard requirement, not just judged: the WCAG failure phrase must be gone.
    assert "click here" not in lowered and lowered.strip() != "here"
    verdict = judge(
        output,
        criteria=(
            "Good link text describes the link's destination or purpose (the "
            "10-K filing / annual report), is concise (2-6 words), and avoids "
            "non-descriptive phrases like 'click here' or 'read more'."
        ),
        context=context,
    )
    assert verdict.passed, f"Link text quality below threshold:\n{verdict.explain()}"
