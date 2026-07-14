# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Phase 4 — shared CSS dimension parsing unit tests.

Covers declared_dimension (style + min-* + legacy attribute) and
strip_undersized_dimensions, including the !important case that the
target-size remediation fix depends on.
"""

from bs4 import BeautifulSoup

from content_accessibility_utility_on_aws.utils.css_dimensions import (
    declared_dimension,
    strip_undersized_dimensions,
)
from content_accessibility_utility_on_aws.utils.constants import MIN_TARGET_SIZE_PX


def _el(html):
    return BeautifulSoup(html, "html.parser").find()


def test_declared_dimension_from_style():
    assert declared_dimension(_el("<button style='width:10px'>x</button>"), "width") == 10.0


def test_declared_dimension_prefers_min_dimension():
    el = _el("<button style='width:10px;min-width:30px'>x</button>")
    # min-width sets the rendered floor and is preferred.
    assert declared_dimension(el, "width") == 30.0


def test_declared_dimension_from_html_attribute():
    assert declared_dimension(_el("<a href='/x' height='12'>x</a>"), "height") == 12.0


def test_declared_dimension_none_when_absent():
    assert declared_dimension(_el("<button>x</button>"), "width") is None


def test_declared_dimension_zero_is_returned_not_none():
    # 0 is a real declared size, distinct from "absent".
    assert declared_dimension(_el("<button style='width:0px'>x</button>"), "width") == 0.0


def test_strip_undersized_plain():
    assert strip_undersized_dimensions("width: 10px; color: red", MIN_TARGET_SIZE_PX) == "color: red"


def test_strip_undersized_important():
    # The !important undersized declaration must be removed so the enforced
    # min-width is not overridden.
    assert strip_undersized_dimensions("width: 10px !important", MIN_TARGET_SIZE_PX) == ""


def test_strip_keeps_adequate_size():
    assert strip_undersized_dimensions("width: 30px", MIN_TARGET_SIZE_PX) == "width: 30px"


def test_strip_keeps_unrelated_declarations():
    result = strip_undersized_dimensions("color: blue; padding: 2px", MIN_TARGET_SIZE_PX)
    assert "color: blue" in result
    assert "padding: 2px" in result


def test_declared_dimension_ignores_hyphenated_property():
    # "max-width" must not be read as "width" (substring false positive).
    assert declared_dimension(_el("<button style='max-width: 10px'>x</button>"), "width") is None


def test_strip_undersized_min_dimension():
    # The audit detects undersizing via min-* first, so an undersized
    # min-width/min-height must also be stripped (including !important), or it
    # would survive alongside the re-added min-width: 24px.
    assert strip_undersized_dimensions("min-width: 10px !important", MIN_TARGET_SIZE_PX) == ""
    assert strip_undersized_dimensions("min-height: 10px", MIN_TARGET_SIZE_PX) == ""


def test_strip_keeps_adequate_min_dimension():
    assert strip_undersized_dimensions("min-width: 30px", MIN_TARGET_SIZE_PX) == "min-width: 30px"
