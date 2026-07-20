# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Build a single multilingual HTML document with an accessible language selector.

Given the source HTML plus one translated copy per target language, this module
assembles one standalone HTML file that contains every language as a hidden
section and shows exactly one at a time. It adds:

* an accessible ``<select>`` language switcher (labeled, keyboard operable),
* browser-language auto-detection on first load (``navigator.languages``),
  which honors the visitor's own preference without a network round trip, and
* per-language ``lang``/``dir`` attributes on each section (WCAG 3.1.2,
  Language of Parts) so assistive tech announces each block correctly.

The switcher and detection are progressive enhancements: with JavaScript
disabled, all languages remain in the document and the first (default) one is
visible, so content is never hidden from a no-JS or crawler client.
"""

import json
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

from content_accessibility_utility_on_aws.i18n.languages import (
    display_name,
    is_rtl,
    normalize_lang_code,
)
from content_accessibility_utility_on_aws.utils.logging_helper import setup_logger

logger = setup_logger(__name__)


def _json_for_script(value: Any) -> str:
    """Serialize ``value`` to JSON safe to embed inside an inline ``<script>``.

    The data embedded here (document ``<title>`` text and language codes) can
    originate from an untrusted source document, and the HTML parser does NOT
    HTML-escape the contents of a ``<script>`` element. Plain ``json.dumps``
    escapes quotes/backslashes but leaves ``</`` intact, so a ``</script>`` (or
    ``<!--``/``<script`` HTML-comment trick) in the data would terminate the
    script element and allow arbitrary markup/JS execution (stored XSS).

    Escaping ``<``, ``>`` and ``&`` as ``\\u00xx`` (and the JS line separators
    U+2028/U+2029) keeps the JSON semantically identical while making it
    impossible to break out of the script context. This is the same technique
    Django's ``json_script`` and Rails' ``json_escape`` use.
    """
    encoded = json.dumps(value, ensure_ascii=False)
    # <, >, & terminate the <script> element or start comment/CDATA tricks;
    # U+2028/U+2029 are valid JSON but break bare JS string literals.
    for char, escape in (
        ("<", "\\u003c"),
        (">", "\\u003e"),
        ("&", "\\u0026"),
        ("\u2028", "\\u2028"),
        ("\u2029", "\\u2029"),
    ):
        encoded = encoded.replace(char, escape)
    return encoded


# Label shown next to the selector, per language. Falls back to English.
_SELECTOR_LABELS: Dict[str, str] = {
    "en": "Language",
    "es": "Idioma",
    "fr": "Langue",
    "de": "Sprache",
    "pt": "Idioma",
    "it": "Lingua",
    "nl": "Taal",
    "ja": "言語",
    "ko": "언어",
    "zh": "语言",
    "ar": "اللغة",
    "ru": "Язык",
    "hi": "भाषा",
}


def _selector_label(lang: str) -> str:
    """Return a localized 'Language' label for the selector."""
    from content_accessibility_utility_on_aws.i18n.languages import primary_subtag

    return _SELECTOR_LABELS.get(primary_subtag(lang), _SELECTOR_LABELS["en"])


def build_multilingual_html(
    versions: Dict[str, str],
    default_lang: str,
    add_selector: bool = True,
    use_browser_language: bool = True,
) -> str:
    """Assemble one HTML document containing all language versions.

    Args:
        versions: Mapping of BCP-47 language code -> full HTML string for that
            language. Must be non-empty.
        default_lang: Language shown when no browser preference matches (and the
            visible one with JS disabled).
        add_selector: Include the visible ``<select>`` language switcher.
        use_browser_language: Emit the auto-detection script that picks the best
            match for ``navigator.languages`` on first load.

    Returns:
        A complete standalone HTML document as a string.
    """
    if not versions:
        raise ValueError("At least one language version is required")

    versions = {normalize_lang_code(k): v for k, v in versions.items()}
    default_lang = normalize_lang_code(default_lang)
    if default_lang not in versions:
        default_lang = next(iter(versions))

    # Order: default first, then the rest in insertion order.
    ordered_langs = [default_lang] + [c for c in versions if c != default_lang]

    # Base the shell on the default version's <head> so title/styles carry over.
    base_soup = BeautifulSoup(versions[default_lang], "html.parser")
    out = BeautifulSoup(
        "<!DOCTYPE html><html><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        "</head><body></body></html>",
        "html.parser",
    )
    out.html["lang"] = default_lang
    if is_rtl(default_lang):
        out.html["dir"] = "rtl"

    # Carry over the default document's <head> children (title, styles, meta).
    if base_soup.head is not None:
        for child in list(base_soup.head.children):
            if getattr(child, "name", None) == "meta" and (
                child.get("charset")
                or child.get("name", "").lower() == "viewport"
            ):
                continue  # already added to the shell
            out.head.append(child)

    out.head.append(_build_style(out))

    body = out.body
    if add_selector:
        body.append(_build_selector(out, ordered_langs, default_lang))

    # One <section> per language, only the default visible initially. Also
    # capture each version's translated <title> so the script can localize the
    # browser-tab / document title when the language changes (WCAG 2.4.2).
    titles: Dict[str, str] = {}
    for lang in ordered_langs:
        lang_soup = BeautifulSoup(versions[lang], "html.parser")
        if lang_soup.title is not None and lang_soup.title.string:
            titles[lang] = lang_soup.title.string.strip()

        section = out.new_tag("section")
        section["class"] = "i18n-lang"
        section["data-lang"] = lang
        section["lang"] = lang
        if is_rtl(lang):
            section["dir"] = "rtl"
        if lang != default_lang:
            section["hidden"] = ""
        source_body = lang_soup.body if lang_soup.body is not None else lang_soup
        for child in list(source_body.children):
            section.append(child)
        body.append(section)

    if use_browser_language or add_selector:
        body.append(
            _build_script(
                out, ordered_langs, default_lang, use_browser_language, titles
            )
        )

    return str(out)


def _build_style(out) -> "BeautifulSoup":
    style = out.new_tag("style")
    style.string = (
        ".i18n-lang[hidden]{display:none}"
        ".i18n-controls{margin:0 0 1rem 0;padding:.5rem;"
        "font-family:system-ui,-apple-system,sans-serif}"
        ".i18n-controls label{margin-inline-end:.5rem;font-weight:600}"
        ".i18n-controls select{padding:.25rem .5rem;font-size:1rem}"
    )
    return style


def _build_selector(out, ordered_langs: List[str], default_lang: str):
    """Build the accessible, labeled language ``<select>`` control."""
    container = out.new_tag("div")
    container["class"] = "i18n-controls"

    label = out.new_tag("label")
    label["for"] = "i18n-language-select"
    label.string = _selector_label(default_lang)
    container.append(label)

    select = out.new_tag("select")
    select["id"] = "i18n-language-select"
    # Announce the control's purpose to assistive tech.
    select["aria-label"] = _selector_label(default_lang)
    for lang in ordered_langs:
        option = out.new_tag("option")
        option["value"] = lang
        option["lang"] = lang
        if lang == default_lang:
            option["selected"] = ""
        # Label each option in its own language (endonym) — the accessible
        # convention so a speaker recognizes their language.
        option.string = display_name(lang)
        select.append(option)
    container.append(select)
    return container


def _build_script(
    out,
    ordered_langs: List[str],
    default_lang: str,
    use_browser_language: bool,
    titles: Dict[str, str],
):
    """Emit the switcher + optional browser-language auto-detection script.

    Language matching is case-insensitive on both sides: ``navigator.languages``
    values (e.g. ``pt-BR``) are lowercased and compared against a lowercased
    index of the available codes, so a region-tagged request matches its
    normalized variant exactly instead of falling through to primary-subtag
    matching. This mirrors the server-side ``negotiate_language`` behavior.
    """
    script = out.new_tag("script")
    langs_json = _json_for_script(ordered_langs)
    default_json = _json_for_script(default_lang)
    titles_json = _json_for_script(titles)
    auto = "true" if use_browser_language else "false"
    script.string = (
        "(function(){\n"
        f"  var LANGS={langs_json};\n"
        f"  var DEFAULT={default_json};\n"
        f"  var TITLES={titles_json};\n"
        f"  var USE_BROWSER={auto};\n"
        "  var sections=document.querySelectorAll('.i18n-lang');\n"
        "  var select=document.getElementById('i18n-language-select');\n"
        "  function primary(c){return (c||'').toLowerCase().split('-')[0];}\n"
        # Lowercase -> canonical code, so an exact match survives casing diffs
        # (browser 'pt-br' vs available 'pt-BR').
        "  var BY_LOWER={};\n"
        "  LANGS.forEach(function(l){BY_LOWER[l.toLowerCase()]=l;});\n"
        "  function show(lang){\n"
        "    if(LANGS.indexOf(lang)===-1){lang=DEFAULT;}\n"
        "    sections.forEach(function(s){\n"
        "      var on=s.getAttribute('data-lang')===lang;\n"
        "      if(on){s.removeAttribute('hidden');}else{s.setAttribute('hidden','');}\n"
        "    });\n"
        "    document.documentElement.setAttribute('lang',lang);\n"
        "    if(TITLES[lang]){document.title=TITLES[lang];}\n"
        "    if(select){select.value=lang;}\n"
        "    try{localStorage.setItem('i18n-lang',lang);}catch(e){}\n"
        "  }\n"
        "  function pick(){\n"
        "    var saved=null;\n"
        "    try{saved=localStorage.getItem('i18n-lang');}catch(e){}\n"
        "    if(saved&&LANGS.indexOf(saved)!==-1){return saved;}\n"
        "    if(USE_BROWSER&&navigator.languages){\n"
        "      for(var i=0;i<navigator.languages.length;i++){\n"
        "        var want=navigator.languages[i].toLowerCase();\n"
        "        if(BY_LOWER[want]){return BY_LOWER[want];}\n"
        "        for(var j=0;j<LANGS.length;j++){\n"
        "          if(primary(LANGS[j])===primary(want)){return LANGS[j];}\n"
        "        }\n"
        "      }\n"
        "    }\n"
        "    return DEFAULT;\n"
        "  }\n"
        "  if(select){select.addEventListener('change',function(){show(select.value);});}\n"
        "  show(pick());\n"
        "})();"
    )
    return script
