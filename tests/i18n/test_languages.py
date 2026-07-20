# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Offline unit tests for the i18n language-code helpers.

These are pure functions with no AWS or browser dependency, so they can be
asserted exactly. They exercise the built-in fallback path (they pass whether
or not the optional ``babel`` dependency is installed).
"""

from content_accessibility_utility_on_aws.i18n.languages import (
    display_name,
    is_rtl,
    normalize_lang_code,
    primary_subtag,
)


def test_normalize_lang_code_region_uppercased():
    assert normalize_lang_code("pt_br") == "pt-BR"
    assert normalize_lang_code("EN") == "en"
    assert normalize_lang_code("zh-hant") == "zh-Hant"


def test_normalize_lang_code_empty():
    assert normalize_lang_code("") == ""
    assert normalize_lang_code(None) == ""


def test_primary_subtag():
    assert primary_subtag("pt-BR") == "pt"
    assert primary_subtag("EN-US") == "en"


def test_is_rtl():
    assert is_rtl("ar") is True
    assert is_rtl("he-IL") is True
    assert is_rtl("en") is False
    assert is_rtl("fr") is False


def test_display_name_fallback_endonym():
    # Native endonym by default (accessible convention for a selector).
    assert display_name("es") == "Español"
    # English name when explicitly requested.
    assert display_name("fr", in_locale="en") == "French"
