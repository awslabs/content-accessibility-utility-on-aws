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
    negotiate_language,
    normalize_lang_code,
    parse_accept_language,
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


def test_parse_accept_language_orders_by_quality():
    parsed = parse_accept_language("en-US,en;q=0.9,es;q=0.8")
    assert parsed == [("en-US", 1.0), ("en", 0.9), ("es", 0.8)]


def test_parse_accept_language_skips_wildcard_and_blank():
    assert parse_accept_language("") == []
    assert parse_accept_language("*") == []


def test_negotiate_language_exact_match():
    assert negotiate_language("es-ES,es;q=0.9", ["en", "es", "fr"]) == "es"


def test_negotiate_language_primary_subtag_match():
    # Browser asks for fr-CA; only fr is available -> match by primary subtag.
    assert negotiate_language("fr-CA,fr;q=0.9", ["en", "es", "fr"], "en") == "fr"


def test_negotiate_language_default_when_no_match():
    assert negotiate_language("de", ["en", "es"], "en") == "en"
    # No default provided -> first available.
    assert negotiate_language("de", ["es", "en"]) == "es"


def test_parse_accept_language_excludes_q0():
    # q=0 means "not acceptable" (RFC 7231) and must be dropped.
    parsed = parse_accept_language("de;q=0,en;q=0.5")
    assert parsed == [("en", 0.5)]


def test_negotiate_language_never_selects_q0():
    # German is explicitly rejected (q=0); even though it is available it must
    # not be chosen — fall back to the default instead.
    assert negotiate_language("de;q=0,en;q=0.5", ["de"], "en") == "en"
