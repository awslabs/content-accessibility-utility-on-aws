# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Implementation of the i18n (translation) API.

``translate_html_accessibility`` translates an HTML file (or a directory of
HTML files) into one or more target languages. Output is either one file per
language, or — when ``multilingual`` is requested — a single document with an
accessible language selector and browser-language auto-detection.
"""

import os
from typing import Any, Dict, List, Optional

from content_accessibility_utility_on_aws.i18n.language_selector import (
    build_multilingual_html,
)
from content_accessibility_utility_on_aws.i18n.languages import normalize_lang_code
from content_accessibility_utility_on_aws.i18n.translator import (
    HTMLTranslator,
    detect_language,
)
from content_accessibility_utility_on_aws.utils.logging_helper import (
    setup_logger,
    TranslationError,
)
from content_accessibility_utility_on_aws.utils.resources import ensure_directory
from content_accessibility_utility_on_aws.utils.constants import (
    DEFAULT_TRANSLATION_BATCH_SIZE,
)

logger = setup_logger(__name__)

# BCP-47 "undetermined" primary tag, used to label the original content in a
# multilingual document when the source language could not be detected. It is a
# valid language subtag, so the emitted markup stays spec-compliant.
UNDETERMINED_LANG = "und"


def _parse_target_languages(options: Dict[str, Any]) -> List[str]:
    """Extract and normalize the list of target languages from options."""
    langs = options.get("target_languages") or options.get("target_language")
    if isinstance(langs, str):
        langs = [part.strip() for part in langs.split(",") if part.strip()]
    if not langs:
        raise TranslationError(
            "No target language specified. Provide target_languages "
            "(e.g. ['es', 'fr']) in options."
        )
    seen: List[str] = []
    for code in langs:
        norm = normalize_lang_code(code)
        if norm and norm not in seen:
            seen.append(norm)
    if not seen:
        raise TranslationError("No valid target languages after normalization")
    return seen


def translate_html_accessibility(
    html_path: str,
    options: Optional[Dict[str, Any]] = None,
    output_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Translate an HTML document into one or more target languages.

    Args:
        html_path: Path to an HTML file, or a directory of HTML files (e.g.
            multi-page converter output) in which case every ``.html`` file is
            translated so no page is dropped.
        options: Translation options:
            - target_languages (list[str] | str): Required. BCP-47 codes, or a
              comma-separated string.
            - source_language (str): Source language; auto-detected if omitted.
            - multilingual (bool): Emit one combined document with a language
              selector instead of one file per language. Default: False.
            - add_language_selector (bool): Include the visible selector in the
              multilingual output. Default: True.
            - use_browser_language (bool): Auto-select the visitor's browser
              language on first load. Default: True.
            - batch_size (int): Segments per model call. Default: 20.
            - model_id (str): Bedrock model id override (uses the default when
              omitted).
            - profile (str): AWS profile for Bedrock credentials.
        output_path: Output file (multilingual) or directory (per-language).

    Returns:
        Dict with ``source_language``, ``target_languages``, ``multilingual``,
        and ``output_files``. For single-file input ``output_files`` is a flat
        mapping of language -> path (with ``multilingual`` as the key in
        combined mode). For a directory input it is nested per source-file stem:
        ``{stem: {language: path}}``.

    Raises:
        FileNotFoundError: If ``html_path`` does not exist.
        TranslationError: On missing/invalid languages or translation failure.
    """
    options = options or {}
    if not os.path.exists(html_path):
        raise FileNotFoundError(f"HTML path not found: {html_path}")

    target_languages = _parse_target_languages(options)

    # Resolve every HTML file to translate. A directory (e.g. multi-page
    # converter output) yields all its .html files so no page is silently
    # dropped; a single file yields just itself.
    source_files = _resolve_source_files(html_path)
    single_file = len(source_files) == 1

    # Detect the source language once, from the first file — pages of one
    # document share a language. An explicit option always wins.
    source_language = options.get("source_language")
    if source_language:
        source_language = normalize_lang_code(source_language)
    else:
        with open(source_files[0], "r", encoding="utf-8") as f:
            source_language = detect_language(f.read())
        if source_language:
            logger.info("Auto-detected source language: %s", source_language)

    translator = HTMLTranslator(
        translate_fn=options.get("translate_fn"),
        source_lang=source_language,
        batch_size=int(options.get("batch_size", DEFAULT_TRANSLATION_BATCH_SIZE)),
        model_id=options.get("model_id"),
        profile=options.get("profile"),
    )

    multilingual = bool(options.get("multilingual", False))
    add_selector = bool(options.get("add_language_selector", True))
    use_browser_language = bool(options.get("use_browser_language", True))

    result: Dict[str, Any] = {
        "source_language": source_language,
        "target_languages": target_languages,
        "multilingual": multilingual,
        "output_files": {},
    }

    for source_file in source_files:
        with open(source_file, "r", encoding="utf-8") as f:
            source_html = f.read()

        versions = _translate_one_file(
            translator, source_html, target_languages, source_language
        )

        if multilingual:
            combined = _assemble_multilingual(
                versions,
                source_html,
                source_language,
                add_selector=add_selector,
                use_browser_language=use_browser_language,
            )
            out_file = _multilingual_output_path(output_path, source_file, single_file)
            _write(out_file, combined)
            _record_output(result, single_file, source_file, "multilingual", out_file)
            logger.info("Wrote multilingual document to %s", out_file)
        else:
            for lang, html in versions.items():
                out_file = _per_language_output_path(
                    output_path, source_file, lang, single_file
                )
                _write(out_file, html)
                _record_output(result, single_file, source_file, lang, out_file)
                logger.info("Wrote %s translation to %s", lang, out_file)

    return result


def _translate_one_file(
    translator: HTMLTranslator,
    source_html: str,
    target_languages: List[str],
    source_language: Optional[str],
) -> Dict[str, str]:
    """Translate one document into every target language.

    A target equal to the source is passed through unchanged (no model call).
    All other languages are translated in a single extract-once pass.
    """
    to_translate = [
        lang
        for lang in target_languages
        if not (source_language and lang == source_language)
    ]
    versions: Dict[str, str] = {}
    if to_translate:
        logger.info("Translating content to %s", ", ".join(to_translate))
        versions.update(translator.translate_to_languages(source_html, to_translate))
    for lang in target_languages:
        if source_language and lang == source_language:
            logger.info("Target %s equals source; using source unchanged", lang)
            versions[lang] = source_html
    return versions


def _assemble_multilingual(
    versions: Dict[str, str],
    source_html: str,
    source_language: Optional[str],
    add_selector: bool,
    use_browser_language: bool,
) -> str:
    """Build a multilingual document, always including the source as an option.

    The original content is added as a selectable language so it is never lost —
    labeled with the detected source language, or the BCP-47 "undetermined"
    tag (``und``) when detection failed. The source is the default shown.
    """
    combined_versions = dict(versions)
    default_lang = source_language or UNDETERMINED_LANG
    if default_lang not in combined_versions:
        combined_versions[default_lang] = source_html
    return build_multilingual_html(
        versions=combined_versions,
        default_lang=default_lang,
        add_selector=add_selector,
        use_browser_language=use_browser_language,
    )


def _record_output(
    result: Dict[str, Any],
    single_file: bool,
    source_file: str,
    key: str,
    out_file: str,
) -> None:
    """Record an output path in the result.

    For single-file input the mapping stays flat (``{lang: path}`` /
    ``{"multilingual": path}``) for backward compatibility. For a multi-file
    (directory) input it is nested per source file so no page is masked.
    """
    output_files = result["output_files"]
    if single_file:
        output_files[key] = out_file
    else:
        stem = os.path.splitext(os.path.basename(source_file))[0]
        output_files.setdefault(stem, {})[key] = out_file


def _resolve_source_files(html_path: str) -> List[str]:
    """Return every HTML file to translate.

    A single file yields just itself. A directory yields all its ``.html``
    files (recursively), sorted, so a multi-page document is fully translated
    rather than collapsing to one "main" page.
    """
    if os.path.isfile(html_path):
        return [html_path]

    html_files: List[str] = []
    for root, _dirs, files in os.walk(html_path):
        for name in sorted(files):
            if name.lower().endswith(".html"):
                html_files.append(os.path.join(root, name))
    if not html_files:
        raise FileNotFoundError(f"No HTML file found in directory: {html_path}")
    return sorted(html_files)


def _multilingual_output_path(
    output_path: Optional[str], source_file: str, single_file: bool
) -> str:
    base = os.path.splitext(os.path.basename(source_file))[0]
    filename = f"{base}_multilingual.html"
    if not output_path:
        return os.path.join(os.path.dirname(source_file) or ".", filename)
    # Treat the path as the output file only when it looks like one (an .html
    # name) and the input was a single file. Otherwise — an existing directory,
    # a trailing separator, an extensionless path (e.g. the CLI default
    # "<base>_translated"), or multi-file input — place the file inside it.
    looks_like_file = single_file and output_path.lower().endswith(".html")
    if looks_like_file:
        return output_path
    return os.path.join(output_path, filename)


def _per_language_output_path(
    output_path: Optional[str], source_file: str, lang: str, single_file: bool
) -> str:
    base = os.path.splitext(os.path.basename(source_file))[0]
    filename = f"{base}.{lang}.html"
    if not output_path:
        return os.path.join(os.path.dirname(source_file) or ".", filename)
    # For per-language output the path is treated as a directory.
    return os.path.join(output_path, filename)


def _write(path: str, content: str) -> None:
    directory = os.path.dirname(path)
    if directory:
        ensure_directory(directory)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
