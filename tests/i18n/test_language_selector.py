# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Offline unit tests for the multilingual document builder / language selector.
"""

import pytest

from content_accessibility_utility_on_aws.i18n.language_selector import (
    build_multilingual_html,
)


def _doc(lang, body):
    return (
        f'<!DOCTYPE html><html lang="{lang}"><head><title>{lang}</title></head>'
        f"<body>{body}</body></html>"
    )


VERSIONS = {
    "en": _doc("en", "<h1>Hello</h1>"),
    "es": _doc("es", "<h1>Hola</h1>"),
    "ar": _doc("ar", "<h1>مرحبا</h1>"),
}


def test_all_languages_present():
    out = build_multilingual_html(VERSIONS, default_lang="en")
    assert 'data-lang="en"' in out
    assert 'data-lang="es"' in out
    assert 'data-lang="ar"' in out


def test_default_visible_others_hidden():
    out = build_multilingual_html(VERSIONS, default_lang="en")
    # The default section is not hidden; non-default sections carry hidden.
    assert out.count("hidden") >= 2  # es and ar hidden
    assert 'lang="en"' in out


def test_selector_present_by_default():
    out = build_multilingual_html(VERSIONS, default_lang="en")
    assert 'id="i18n-language-select"' in out
    assert '<label for="i18n-language-select"' in out


def test_selector_can_be_omitted():
    out = build_multilingual_html(VERSIONS, default_lang="en", add_selector=False)
    assert 'id="i18n-language-select"' not in out


def test_browser_language_detection_script():
    out = build_multilingual_html(VERSIONS, default_lang="en", use_browser_language=True)
    assert "navigator.languages" in out


def test_browser_language_can_be_disabled():
    out = build_multilingual_html(
        VERSIONS, default_lang="en", add_selector=True, use_browser_language=False
    )
    # Script still present for the selector, but auto-detect flag is off.
    assert "var USE_BROWSER=false" in out


def test_rtl_section_gets_dir():
    out = build_multilingual_html(VERSIONS, default_lang="en")
    assert 'dir="rtl"' in out  # the Arabic section


def test_unknown_default_falls_back_to_first():
    out = build_multilingual_html(VERSIONS, default_lang="zz")
    # Falls back to the first available language without raising.
    assert 'id="i18n-language-select"' in out


def test_empty_versions_raises():
    with pytest.raises(ValueError):
        build_multilingual_html({}, default_lang="en")


def test_region_code_matched_case_insensitively():
    # Browser 'pt-br' must match available 'pt-BR' exactly via the lowercase
    # index, not fall through to primary-subtag matching.
    versions = {"pt-BR": _doc("pt-BR", "<h1>Oi</h1>"), "pt-PT": _doc("pt-PT", "<h1>Ola</h1>")}
    out = build_multilingual_html(versions, default_lang="pt-BR")
    assert "BY_LOWER" in out
    assert "l.toLowerCase()" in out


def test_malicious_title_cannot_break_out_of_script():
    # A </script> in an untrusted source <title> must not terminate the inline
    # script block (stored XSS). It should be unicode-escaped in the JSON blob.
    payload = "</script><img src=x onerror=alert(1)>"
    versions = {
        "en": (
            '<!DOCTYPE html><html lang="en"><head>'
            f"<title>{payload}</title></head><body><h1>Hi</h1></body></html>"
        ),
        "es": _doc("es", "<h1>Hola</h1>"),
    }
    out = build_multilingual_html(versions, default_lang="en")
    assert payload not in out
    assert "\\u003c/script\\u003e" in out


def test_malicious_language_code_cannot_break_out_of_script():
    # A language code carrying a script-breakout payload (e.g. from a crafted
    # <html lang>) must be escaped where it is embedded in the inline script.
    mal_lang = 'en"];</script><script>alert(document.cookie)//'
    doc = "<html><head><title>T</title></head><body><h1>Hi</h1></body></html>"
    out = build_multilingual_html({mal_lang: doc, "es": doc}, default_lang=mal_lang)
    assert "</script><script>alert(document.cookie)" not in out


def test_per_language_title_localized_in_script():
    versions = {
        "en": _doc("en", "<h1>Hello</h1>").replace("<title>en</title>", "<title>Report</title>"),
        "es": _doc("es", "<h1>Hola</h1>").replace("<title>es</title>", "<title>Informe</title>"),
    }
    out = build_multilingual_html(versions, default_lang="en")
    # Titles map is emitted and document.title is swapped on language change.
    assert "Informe" in out
    assert "document.title=TITLES[lang]" in out
