# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Phase 1 — color contrast math unit tests.

The contrast ratio calculation is deterministic and has known reference values
(WCAG defines black-on-white as 21:1 and identical colors as 1:1), so it can be
asserted exactly without any document or AWS dependency.
"""

import pytest
from bs4 import BeautifulSoup

from content_accessibility_utility_on_aws.audit.checks.color_contrast_checks import (
    ColorContrastCheck,
)


@pytest.fixture
def check():
    # The check only needs a soup and a no-op issue callback for these helpers.
    return ColorContrastCheck(BeautifulSoup("<html></html>", "html.parser"), lambda *a, **k: None)


def test_black_on_white_is_max_ratio(check):
    ratio = check._calculate_contrast_ratio("#000000", "#FFFFFF")
    assert ratio == pytest.approx(21.0, abs=0.1)


def test_white_on_black_is_symmetric(check):
    # Ratio is order-independent.
    assert check._calculate_contrast_ratio("#FFFFFF", "#000000") == pytest.approx(21.0, abs=0.1)


def test_identical_colors_is_one(check):
    assert check._calculate_contrast_ratio("#777777", "#777777") == pytest.approx(1.0, abs=0.001)


def test_hex_to_rgb(check):
    assert check._hex_to_rgb("#FF8000") == (255, 128, 0)
    assert check._hex_to_rgb("000000") == (0, 0, 0)


def test_known_mid_contrast_pair(check):
    # Mid-grey on white is a well-defined ratio comfortably above 1 and below 21.
    ratio = check._calculate_contrast_ratio("#767676", "#FFFFFF")
    assert 4.0 < ratio < 5.0
