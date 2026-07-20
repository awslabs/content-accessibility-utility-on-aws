# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Language code helpers for the i18n package.

Normalizes user-supplied language codes to BCP-47, resolves human-readable
display names, and negotiates a preferred language from an HTTP
``Accept-Language`` header (the value a browser sends).

``babel`` (from the ``[i18n]`` extra) provides accurate, localized display
names and endonyms when installed. When it is absent everything still works
using a small built-in table covering the most common languages, so the core
translation path never hard-depends on ``babel``.
"""

from typing import Dict, List, Optional, Tuple

from content_accessibility_utility_on_aws.utils.logging_helper import setup_logger

logger = setup_logger(__name__)

# Built-in fallback table used when ``babel`` is not installed. Maps a lowercase
# BCP-47 language (or language-region) code to (English name, native endonym).
# Endonyms let the language selector label each option in its own language,
# which is the accessible, user-friendly choice.
_FALLBACK_NAMES: Dict[str, Tuple[str, str]] = {
    "ar": ("Arabic", "العربية"),
    "bn": ("Bengali", "বাংলা"),
    "de": ("German", "Deutsch"),
    "el": ("Greek", "Ελληνικά"),
    "en": ("English", "English"),
    "es": ("Spanish", "Español"),
    "fr": ("French", "Français"),
    "he": ("Hebrew", "עברית"),
    "hi": ("Hindi", "हिन्दी"),
    "id": ("Indonesian", "Bahasa Indonesia"),
    "it": ("Italian", "Italiano"),
    "ja": ("Japanese", "日本語"),
    "ko": ("Korean", "한국어"),
    "nl": ("Dutch", "Nederlands"),
    "pl": ("Polish", "Polski"),
    "pt": ("Portuguese", "Português"),
    "pt-br": ("Portuguese (Brazil)", "Português (Brasil)"),
    "ru": ("Russian", "Русский"),
    "sv": ("Swedish", "Svenska"),
    "th": ("Thai", "ไทย"),
    "tr": ("Turkish", "Türkçe"),
    "uk": ("Ukrainian", "Українська"),
    "vi": ("Vietnamese", "Tiếng Việt"),
    "zh": ("Chinese", "中文"),
    "zh-cn": ("Chinese (Simplified)", "简体中文"),
    "zh-tw": ("Chinese (Traditional)", "繁體中文"),
}

# Languages written right-to-left, keyed by primary subtag. Used to set the
# ``dir="rtl"`` attribute on translated blocks (WCAG-relevant for correct
# rendering and screen-reader behavior).
_RTL_LANGUAGES = {"ar", "he", "fa", "ur", "ps", "sd", "yi", "dv"}


def normalize_lang_code(code: str) -> str:
    """Normalize a language code to BCP-47 form (e.g. ``pt-BR``, ``en``).

    Lowercases the primary language subtag and upper-cases a 2-letter region
    subtag; leaves script subtags (e.g. ``zh-Hant``) title-cased. Whitespace is
    stripped. Returns an empty string for falsy input.
    """
    if not code:
        return ""
    parts = [p for p in code.strip().replace("_", "-").split("-") if p]
    if not parts:
        return ""
    normalized = [parts[0].lower()]
    for part in parts[1:]:
        if len(part) == 2:  # region subtag, e.g. BR, TW
            normalized.append(part.upper())
        elif len(part) == 4:  # script subtag, e.g. Hant
            normalized.append(part.capitalize())
        else:
            normalized.append(part.lower())
    return "-".join(normalized)


def primary_subtag(code: str) -> str:
    """Return the lowercase primary language subtag (``pt`` from ``pt-BR``)."""
    normalized = normalize_lang_code(code)
    return normalized.split("-")[0].lower() if normalized else ""


def is_rtl(code: str) -> bool:
    """Return True if the language is written right-to-left."""
    return primary_subtag(code) in _RTL_LANGUAGES


def display_name(code: str, in_locale: Optional[str] = None) -> str:
    """Return a human-readable display name for a language code.

    Args:
        code: BCP-47 language code.
        in_locale: Locale to render the name in. ``None`` (the default) returns
            the language's own endonym (e.g. ``Español`` for ``es``), which is
            the accessible choice for a language selector. Pass ``"en"`` to
            force English names.

    Uses ``babel`` when available, falling back to a built-in table.
    """
    normalized = normalize_lang_code(code)
    if not normalized:
        return code or ""

    try:
        from babel import Locale  # type: ignore

        locale = Locale.parse(normalized.replace("-", "_"))
        target = in_locale.replace("-", "_") if in_locale else normalized.replace("-", "_")
        name = locale.get_display_name(target)
        if name:
            # Capitalize the first letter; babel returns lowercased names for
            # some locales.
            return name[0].upper() + name[1:]
    except Exception as e:  # noqa: BLE001 - babel absent or unknown code
        logger.debug("babel display name unavailable for %s: %s", normalized, e)

    key = normalized.lower()
    if key in _FALLBACK_NAMES:
        english, native = _FALLBACK_NAMES[key]
        return english if in_locale == "en" else native
    # Fall back to the primary subtag, then the raw code.
    prim = primary_subtag(normalized)
    if prim in _FALLBACK_NAMES:
        english, native = _FALLBACK_NAMES[prim]
        return english if in_locale == "en" else native
    return normalized


def parse_accept_language(header: str) -> List[Tuple[str, float]]:
    """Parse an HTTP ``Accept-Language`` header into (code, quality) pairs.

    Returns the languages sorted by descending quality (``q``) value. Malformed
    entries are skipped, and entries with ``q=0`` (RFC 7231 "not acceptable")
    are excluded entirely. Example::

        "en-US,en;q=0.9,es;q=0.8" -> [("en-US", 1.0), ("en", 0.9), ("es", 0.8)]
    """
    if not header:
        return []
    parsed: List[Tuple[str, float]] = []
    for part in header.split(","):
        part = part.strip()
        if not part:
            continue
        tokens = part.split(";")
        code = normalize_lang_code(tokens[0])
        if not code or code == "*":
            continue
        quality = 1.0
        malformed_q = False
        for token in tokens[1:]:
            token = token.strip()
            if token.startswith("q="):
                try:
                    quality = float(token[2:])
                except ValueError:
                    # A malformed q must NOT be promoted to 1.0 (that would let a
                    # garbled entry outrank valid preferences); drop the entry.
                    malformed_q = True
        # Drop entries with a malformed q, or q<=0 (explicit "not acceptable"),
        # so negotiation never selects an unacceptable/garbled language.
        if malformed_q or quality <= 0:
            continue
        parsed.append((code, quality))
    parsed.sort(key=lambda pair: pair[1], reverse=True)
    return parsed


def negotiate_language(
    header: str, available: List[str], default: Optional[str] = None
) -> Optional[str]:
    """Pick the best language from ``available`` for an ``Accept-Language`` header.

    Matches by exact code first, then by primary subtag (so a browser asking for
    ``en-GB`` matches an available ``en``). Returns ``default`` (or the first
    available language when no default is given) if nothing matches.
    """
    available_norm = [normalize_lang_code(c) for c in available]
    fallback = default if default is not None else (available_norm[0] if available_norm else None)
    if not available_norm:
        return fallback

    prim_index: Dict[str, str] = {}
    for code in available_norm:
        prim_index.setdefault(primary_subtag(code), code)

    for code, _q in parse_accept_language(header):
        if code in available_norm:
            return code
        prim = primary_subtag(code)
        if prim in prim_index:
            return prim_index[prim]
    return fallback
