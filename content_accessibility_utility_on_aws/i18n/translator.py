# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
HTML-aware translation backed by Amazon Bedrock.

``HTMLTranslator`` translates the human-visible content of an HTML document
into a target language while leaving the markup structure untouched. It works
at the DOM-node level with BeautifulSoup rather than asking the model to
regenerate whole HTML, which:

* preserves every tag, attribute, class, id and inline style exactly,
* keeps images, scripts, styles and code samples out of the model input
  (text anywhere inside those subtrees is skipped, not just direct children),
* lets translatable attributes (``alt``, ``title``, ``aria-label``,
  ``aria-placeholder``, ``placeholder``) be translated too — important for
  accessibility, since screen readers announce those values, and
* is deterministic and unit-testable offline (the Bedrock call is the only
  networked part and is injected).

Text segments are sent to the model in batches as a JSON array so a single call
translates many nodes, keeping token/latency cost down on large documents.
"""

import json
from typing import Callable, Dict, List, Optional

from bs4 import BeautifulSoup, NavigableString
from bs4.element import (
    Comment,
    Doctype,
    Declaration,
    CData,
    ProcessingInstruction,
)

# Special NavigableString subclasses that carry markup/machinery rather than
# human-visible text and must never be translated.
_NON_CONTENT_STRINGS = (
    Comment,
    Doctype,
    Declaration,
    CData,
    ProcessingInstruction,
)

from content_accessibility_utility_on_aws.i18n.languages import (
    display_name,
    is_rtl,
    normalize_lang_code,
)
from content_accessibility_utility_on_aws.utils.logging_helper import (
    setup_logger,
    TranslationError,
)

logger = setup_logger(__name__)

# Tags whose text content must never be translated (code, scripts, styles,
# and machine-readable values).
_SKIP_CONTENT_TAGS = {"script", "style", "code", "pre", "kbd", "samp", "var"}

# Attributes that hold human-visible / screen-reader-announced text and should
# be translated. ``aria-label`` and friends are announced by assistive tech, so
# translating them keeps the accessible experience localized too.
_TRANSLATABLE_ATTRS = ("alt", "title", "aria-label", "aria-placeholder", "placeholder")

# Default batch size (number of text segments per Bedrock call). Chosen to keep
# each request comfortably within output-token limits while minimizing the
# number of round trips.
DEFAULT_BATCH_SIZE = 40


class HTMLTranslator:
    """Translate the visible content of HTML into a target language.

    Args:
        translate_fn: Callable taking ``(segments, target_lang, source_lang)``
            and returning the translated segments in the same order. Defaults to
            a Bedrock-backed implementation. Injectable for testing offline.
        source_lang: BCP-47 source language, or ``None`` to let the model infer
            it (or auto-detect via :func:`detect_language`).
        batch_size: Number of segments sent per translation call.
    """

    def __init__(
        self,
        translate_fn: Optional[Callable[[List[str], str, Optional[str]], List[str]]] = None,
        source_lang: Optional[str] = None,
        batch_size: int = DEFAULT_BATCH_SIZE,
        model_id: Optional[str] = None,
        profile: Optional[str] = None,
    ):
        # ``model_id``/``profile`` are only used by the default Bedrock
        # translator; an injected ``translate_fn`` (e.g. in tests) ignores them.
        self._translate_fn = translate_fn or _make_bedrock_translate_fn(
            model_id=model_id, profile=profile
        )
        self.source_lang = normalize_lang_code(source_lang) if source_lang else None
        self.batch_size = max(1, int(batch_size))

    def translate_html(self, html: str, target_lang: str) -> str:
        """Return ``html`` with its visible content translated to ``target_lang``.

        The root ``<html lang>`` (and ``dir`` for RTL languages) is updated to
        the target so the output is a valid, accessible standalone document
        (WCAG 3.1.1 Language of Page).
        """
        target_lang = normalize_lang_code(target_lang)
        if not target_lang:
            raise TranslationError("A target language is required for translation")
        return self.translate_to_languages(html, [target_lang])[target_lang]

    def translate_to_languages(
        self, html: str, target_langs: List[str]
    ) -> Dict[str, str]:
        """Translate ``html`` into each language, returning ``{lang: html}``.

        The source is parsed and its translatable segments extracted **once**,
        then each target language reuses that work: only the model call and the
        node reinsertion differ per language. This avoids re-parsing and
        re-walking the identical source document once per language.
        """
        # Extract the segment list a single time from one canonical parse.
        template = BeautifulSoup(html, "html.parser")
        template_text_nodes, template_attr_targets = self._collect_targets(template)
        segments: List[str] = [str(node) for node in template_text_nodes]
        segments.extend(value for _el, _attr, value in template_attr_targets)

        results: Dict[str, str] = {}
        for raw_lang in target_langs:
            target_lang = normalize_lang_code(raw_lang)
            if not target_lang:
                raise TranslationError("A target language is required for translation")

            if not segments:
                logger.debug("No translatable content found for %s", target_lang)
                soup = BeautifulSoup(html, "html.parser")
            else:
                translated = self._translate_segments(segments, target_lang)
                # Re-parse per language so each output gets its own node tree;
                # the offsets line up with the template because the same source
                # produces the same node ordering.
                soup = BeautifulSoup(html, "html.parser")
                text_nodes, attr_targets = self._collect_targets(soup)
                self._reinsert(soup, text_nodes, attr_targets, translated)

            self._set_root_language(soup, target_lang)
            results[target_lang] = str(soup)
        return results

    def translate_soup(self, soup, target_lang: str) -> None:
        """Translate the visible content of a BeautifulSoup tree in place.

        Does not touch the root ``lang``/``dir`` attributes — callers that build
        a multilingual document set those on the per-language container instead.
        """
        target_lang = normalize_lang_code(target_lang)
        text_nodes, attr_targets = self._collect_targets(soup)

        segments: List[str] = [str(node) for node in text_nodes]
        segments.extend(value for _el, _attr, value in attr_targets)
        if not segments:
            logger.debug("No translatable content found for %s", target_lang)
            return

        translated = self._translate_segments(segments, target_lang)
        self._reinsert(soup, text_nodes, attr_targets, translated)

    @staticmethod
    def _set_root_language(soup, target_lang: str) -> None:
        """Set ``lang``/``dir`` on the root ``<html>`` for a standalone document."""
        root = soup.find("html")
        if root is None:
            return
        root["lang"] = target_lang
        if is_rtl(target_lang):
            root["dir"] = "rtl"
        elif root.get("dir") == "rtl":
            del root["dir"]

    @staticmethod
    def _reinsert(soup, text_nodes, attr_targets, translated: List[str]) -> None:
        """Write translated segments back into their text nodes and attributes."""
        # Reinsert text nodes, preserving surrounding whitespace.
        for node, new_text in zip(text_nodes, translated[: len(text_nodes)]):
            leading = node[: len(node) - len(node.lstrip())]
            trailing = node[len(node.rstrip()):]
            node.replace_with(NavigableString(leading + new_text.strip() + trailing))

        # Reinsert translated attribute values.
        attr_translations = translated[len(text_nodes):]
        for (element, attr, _orig), new_value in zip(attr_targets, attr_translations):
            element[attr] = new_value

    def _collect_targets(self, soup):
        """Gather translatable text nodes and (element, attr, value) tuples."""
        text_nodes: List[NavigableString] = []
        for node in soup.find_all(string=True):
            if isinstance(node, _NON_CONTENT_STRINGS):
                continue
            if not node.strip():
                continue
            # Skip text anywhere inside a code/script/style subtree, not just
            # when it is the immediate parent — a highlighted <pre><span>...
            # must stay verbatim.
            if _has_skip_content_ancestor(node):
                continue
            # Respect an explicit opt-out (translate="no" per the HTML spec).
            if _has_translate_no_ancestor(node):
                continue
            text_nodes.append(node)

        attr_targets = []
        for element in soup.find_all(True):
            # Honor translate="no" on the element OR any ancestor, matching how
            # text nodes are treated.
            if _has_translate_no_self_or_ancestor(element):
                continue
            for attr in _TRANSLATABLE_ATTRS:
                value = element.get(attr)
                if isinstance(value, str) and value.strip():
                    attr_targets.append((element, attr, value))
        return text_nodes, attr_targets

    def _translate_segments(self, segments: List[str], target_lang: str) -> List[str]:
        """Translate all segments in order, batching the model calls."""
        results: List[str] = []
        for start in range(0, len(segments), self.batch_size):
            batch = segments[start : start + self.batch_size]
            translated = self._translate_fn(batch, target_lang, self.source_lang)
            if len(translated) != len(batch):
                raise TranslationError(
                    "Translator returned %d segments for a batch of %d"
                    % (len(translated), len(batch))
                )
            results.extend(translated)
        return results


def _has_translate_no_ancestor(node) -> bool:
    """True if any ancestor of a text node carries ``translate="no"``."""
    element = node.parent
    while element is not None and getattr(element, "get", None) is not None:
        if _element_opts_out(element):
            return True
        element = element.parent
    return False


def _has_translate_no_self_or_ancestor(element) -> bool:
    """True if the element or any ancestor carries ``translate="no"``.

    Used for translatable attributes so ``translate="no"`` on a container opts
    out the ``alt``/``title``/``aria-label`` of descendants too, matching how
    text nodes are handled.
    """
    current = element
    while current is not None and getattr(current, "get", None) is not None:
        if _element_opts_out(current):
            return True
        current = current.parent
    return False


def _has_skip_content_ancestor(node) -> bool:
    """True if the text node sits anywhere inside a skip-content tag.

    Walks the full ancestor chain (not just the immediate parent) so text
    nested inside ``<pre>``/``<code>``/``<script>`` via inline wrappers (e.g. a
    syntax-highlighted ``<pre><span>...``) is still left untranslated.
    """
    element = node.parent
    while element is not None and getattr(element, "name", None) is not None:
        if element.name in _SKIP_CONTENT_TAGS:
            return True
        element = element.parent
    return False


def _element_opts_out(element) -> bool:
    """True if the element opts out of translation via ``translate="no"``."""
    value = element.get("translate")
    return isinstance(value, str) and value.strip().lower() == "no"


def detect_language(html: str) -> Optional[str]:
    """Best-effort detection of the source language of an HTML document.

    Prefers an explicit ``<html lang>`` attribute, then uses ``langdetect``
    (from the ``[i18n]`` extra) on the visible text. Returns ``None`` if the
    language cannot be determined.
    """
    soup = BeautifulSoup(html, "html.parser")
    root = soup.find("html")
    if root is not None and root.get("lang"):
        return normalize_lang_code(root.get("lang"))

    text = " ".join(
        s.strip()
        for s in soup.find_all(string=True)
        if not isinstance(s, _NON_CONTENT_STRINGS)
        and s.strip()
        and (s.parent is None or s.parent.name not in _SKIP_CONTENT_TAGS)
    )[:2000]
    if not text:
        return None
    try:
        from langdetect import detect  # type: ignore

        return normalize_lang_code(detect(text))
    except Exception as e:  # noqa: BLE001 - langdetect absent or detection failed
        logger.debug("Source-language detection unavailable: %s", e)
        return None


def _make_bedrock_translate_fn(
    model_id: Optional[str] = None, profile: Optional[str] = None
) -> Callable[[List[str], str, Optional[str]], List[str]]:
    """Build the default Bedrock-backed translation callable.

    The returned function batches segments into a JSON array, asks the model to
    translate each entry preserving inline placeholders and returning a JSON
    array of the same length, and parses the response. Bedrock access uses the
    core ``boto3`` dependency via the shared :class:`BedrockClient`, so the
    ``[i18n]`` extra is only needed for language names / detection.

    Args:
        model_id: Bedrock model id override. ``None`` uses the shared default.
        profile: AWS profile for credentials. ``None`` uses the default chain.

    The :class:`BedrockClient` is created lazily on the first call and reused
    for every subsequent batch/language, so a multi-batch, multi-language run
    does not rebuild a boto3 client (and lose connection pooling) each time.
    """
    # Mutable single-slot cache closed over by ``_translate`` so the client is
    # built at most once, on first use.
    client_holder: List = []

    def _get_client():
        if not client_holder:
            # Imported lazily so importing the i18n package never eagerly builds
            # a boto3 client (mirrors how remediation constructs clients).
            from content_accessibility_utility_on_aws.remediate.services.bedrock_client import (
                BedrockClient,
            )

            kwargs = {}
            if model_id:
                kwargs["model_id"] = model_id
            if profile:
                kwargs["profile"] = profile
            client_holder.append(BedrockClient(**kwargs))
        return client_holder[0]

    def _translate(
        segments: List[str], target_lang: str, source_lang: Optional[str]
    ) -> List[str]:
        client = _get_client()
        target_name = display_name(target_lang, in_locale="en")
        source_clause = (
            f"from {display_name(source_lang, in_locale='en')} " if source_lang else ""
        )
        system_prompt = (
            "You are a professional localization translator. You translate user "
            "interface and document text accurately and idiomatically while "
            "preserving meaning, tone, and any inline HTML tags or placeholders "
            "exactly as they appear. You never add explanations."
        )
        prompt = (
            f"Translate each string in the following JSON array {source_clause}"
            f"into {target_name} ({target_lang}). Rules:\n"
            "- Return ONLY a JSON array of strings, same length and order as the input.\n"
            "- Preserve any inline HTML tags, entities, and {placeholders} unchanged.\n"
            "- Do not translate proper nouns, code, URLs, or numbers.\n"
            "- Keep leading/trailing punctuation and casing conventions natural "
            "for the target language.\n\n"
            f"Input:\n{json.dumps(segments, ensure_ascii=False)}"
        )

        raw = client.generate_text(
            prompt=prompt,
            purpose="content_translation",
            system_prompt=system_prompt,
        )
        return _parse_translation_array(raw, len(segments), segments)

    return _translate


def _parse_translation_array(
    raw: str, expected: int, fallback: List[str]
) -> List[str]:
    """Parse the model's JSON array reply, tolerating code fences and prose.

    Falls back to the original segments for any that can't be recovered so a
    malformed reply degrades to untranslated text rather than raising and losing
    the whole batch.
    """
    # Isolate the outermost JSON array. Slicing between the first "[" and last
    # "]" already skips any ```json fence, surrounding prose, or trailing fence,
    # so no separate fence-stripping pass is needed.
    text = raw.strip()
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        candidate = text[start : end + 1]
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, list):
                result = [str(item) for item in parsed]
                if len(result) == expected:
                    return result
                logger.warning(
                    "Translation returned %d items, expected %d; padding with "
                    "originals",
                    len(result),
                    expected,
                )
                # Pad/truncate defensively to keep node alignment.
                result = result[:expected]
                result.extend(fallback[len(result):])
                return result
        except json.JSONDecodeError as e:
            logger.warning("Could not parse translation JSON: %s", e)
    logger.warning("Falling back to untranslated text for this batch")
    return list(fallback)
