# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
HTML-aware translation backed by Amazon Bedrock.

``HTMLTranslator`` translates the human-visible content of an HTML document
into a target language while leaving the markup structure untouched. It works
with BeautifulSoup rather than asking the model to regenerate whole HTML, which:

* preserves every tag, attribute, class, id and inline style exactly,
* keeps images, scripts, styles and code samples out of the model input
  (text anywhere inside those subtrees is skipped, not just direct children),
* translates a block's phrasing content as ONE unit — text plus inline
  formatting (``<a>``, ``<strong>``, ...) flattened into a single segment with
  inline elements represented as numbered placeholders — so the model sees the
  whole sentence and can reorder words across a tag boundary (e.g. move a link
  to sentence-final position in Japanese), which per-text-node translation
  cannot do,
* translates screen-reader-announced / user-visible attributes (``alt``,
  ``title``, ``aria-label``, ``<input type=submit> value``, ``<meta
  name=description> content``, ...), and
* is deterministic and unit-testable offline (the Bedrock call is the only
  networked part and is injected).

Segments (one per phrasing run, plus one per translatable attribute) are sent
to the model in batches as a JSON array so a single call translates many at
once, keeping token/latency cost down on large documents.
"""

import copy
import json
from html import escape as _html_escape
from typing import Callable, Dict, List, Optional, Tuple

from bs4 import BeautifulSoup, NavigableString, Tag
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
from content_accessibility_utility_on_aws.utils.constants import (
    DEFAULT_TRANSLATION_BATCH_SIZE,
)

logger = setup_logger(__name__)


class _BatchParseError(Exception):
    """Raised by the default translator when a batch reply can't be parsed.

    Signals the batching loop to split-and-retry (or, at size 1, fall back to
    source for just that segment) rather than silently substituting source text
    for the whole batch. Internal to this module.
    """

    def __init__(self, batch_size: int):
        super().__init__(f"unparseable/truncated reply for a {batch_size}-segment batch")
        self.batch_size = batch_size


# Tags whose text content must never be translated (code, scripts, styles,
# and machine-readable values).
_SKIP_CONTENT_TAGS = {"script", "style", "code", "pre", "kbd", "samp", "var"}

# Phrasing (inline) elements that flow within a line of text. These are folded
# into their surrounding block's translation unit so the model sees the whole
# sentence at once and can reorder words across the tag boundary (e.g. moving a
# link to sentence-final position in Japanese). Their own text IS translated.
_INLINE_TAGS = {
    "a", "abbr", "b", "bdi", "bdo", "cite", "data", "dfn", "em", "i", "label",
    "mark", "q", "rp", "rt", "ruby", "s", "small", "span", "strong", "sub",
    "sup", "time", "u", "font",
}
# Inline elements kept verbatim inside a unit as an opaque placeholder: their
# subtree is preserved unchanged (code samples, and void elements that carry no
# translatable text of their own). ``img``'s ``alt``/``title`` are still
# translated via the attribute pass.
_INLINE_OPAQUE_TAGS = {"code", "kbd", "samp", "var", "br", "img", "wbr"}

# Attributes translated on ANY element (visible or screen-reader-announced
# text). ``aria-label`` and friends are announced by assistive tech, so
# translating them keeps the accessible experience localized too.
_GLOBAL_TRANSLATABLE_ATTRS = (
    "alt", "title", "aria-label", "aria-placeholder", "placeholder",
    "aria-valuetext", "aria-roledescription",
)
# ``<input>`` types whose ``value`` is a user-visible button label (as opposed
# to editable field data, which must NOT be translated).
_BUTTON_INPUT_TYPES = {"submit", "button", "reset"}
# ``<meta>`` name/property values whose ``content`` is user-visible or
# SEO/social text worth localizing.
_TRANSLATABLE_META_NAMES = {"description", "keywords"}
_TRANSLATABLE_META_PROPERTIES = {
    "og:title", "og:description", "og:site_name", "twitter:title",
    "twitter:description",
}

# Placeholder element name used to mark inline formatting inside a translation
# unit sent to the model. Hyphenated so it is a valid custom element that parses
# cleanly and never collides with real HTML tags.
_PLACEHOLDER_TAG = "x-i18n"

# Default batch size (number of text segments per Bedrock call). Sourced from a
# single shared constant so the config defaults, the API layer, and this module
# cannot drift. A truncated batch is split-and-retried (see _translate_batch),
# so this is a starting point, not a hard limit.
DEFAULT_BATCH_SIZE = DEFAULT_TRANSLATION_BATCH_SIZE


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

        Text is segmented at the block level: a block's phrasing content (its
        text plus inline formatting like ``<a>``/``<strong>``) becomes ONE
        segment with inline tags represented as numbered placeholders. The model
        therefore sees the whole sentence and can reorder words across a tag
        boundary (e.g. moving a link to sentence-final position in Japanese),
        which per-text-node translation cannot do.
        """
        # Extract the segment list a single time from one canonical parse.
        template = BeautifulSoup(html, "html.parser")
        template_units, template_attr_targets = self._collect_targets(template)
        segments: List[str] = [u.text for u in template_units]
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
                # units line up with the template because the same source
                # produces the same tree walk.
                soup = BeautifulSoup(html, "html.parser")
                units, attr_targets = self._collect_targets(soup)
                self._reinsert(units, attr_targets, translated)

            self._set_root_language(soup, target_lang)
            results[target_lang] = str(soup)
        return results

    def translate_soup(self, soup, target_lang: str) -> None:
        """Translate the visible content of a BeautifulSoup tree in place.

        Does not touch the root ``lang``/``dir`` attributes — callers that build
        a multilingual document set those on the per-language container instead.
        """
        target_lang = normalize_lang_code(target_lang)
        units, attr_targets = self._collect_targets(soup)

        segments: List[str] = [u.text for u in units]
        segments.extend(value for _el, _attr, value in attr_targets)
        if not segments:
            logger.debug("No translatable content found for %s", target_lang)
            return

        translated = self._translate_segments(segments, target_lang)
        self._reinsert(units, attr_targets, translated)

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

    def _reinsert(self, units, attr_targets, translated: List[str]) -> None:
        """Write translated segments back into their units and attributes.

        Attributes are applied FIRST so that when a unit rebuilds an inline
        element it clones the already-translated attributes (e.g. a link's
        ``title``) rather than the originals.
        """
        unit_count = len(units)
        attr_translations = translated[unit_count:]
        for (element, attr, _orig), new_value in zip(attr_targets, attr_translations):
            element[attr] = new_value

        # Apply units in reverse document order so that when one parent block
        # hosts several runs (separated by nested block children), rebuilding a
        # later run cannot shift the child indices of an earlier one.
        for unit, new_text in reversed(list(zip(units, translated[:unit_count]))):
            unit.apply(new_text)

    def _collect_targets(self, soup):
        """Gather translatable text units and (element, attr, value) tuples.

        A *unit* is a maximal run of phrasing content (text + inline elements)
        directly under a block element, serialized into one placeholder-bearing
        segment. Returns ``(units, attr_targets)``.
        """
        units: List[_TextUnit] = []
        for element in soup.find_all(True):
            # Only block-level, translatable elements host units; inline elements
            # are folded into their block ancestor's unit rather than forming
            # their own (which would re-split the sentence we just joined).
            if _is_inline(element) or element.name in _SKIP_CONTENT_TAGS:
                continue
            if _has_translate_no_self_or_ancestor(element):
                continue
            if _has_skip_content_ancestor_tag(element):
                continue
            units.extend(_build_units_for_block(element))

        attr_targets = _collect_attr_targets(soup)
        return units, attr_targets

    def _translate_segments(self, segments: List[str], target_lang: str) -> List[str]:
        """Translate all segments in order, batching the model calls.

        Each fixed-size batch is translated in one call; if the model reply is
        unparseable or truncated (signalled by ``_BatchParseError`` from the
        default translator), the batch is split in half and retried, down to
        single segments. Only a single segment that still fails falls back to
        its untranslated source — so a truncation affects at most one segment,
        never a whole batch, and the fallback surface is minimal.
        """
        results: List[str] = []
        for start in range(0, len(segments), self.batch_size):
            batch = segments[start : start + self.batch_size]
            results.extend(self._translate_batch(batch, target_lang))
        return results

    def _translate_batch(self, batch: List[str], target_lang: str) -> List[str]:
        """Translate one batch, splitting-and-retrying on a parse/truncation failure."""
        try:
            translated = self._translate_fn(batch, target_lang, self.source_lang)
        except _BatchParseError:
            if len(batch) <= 1:
                logger.warning(
                    "Translation failed for a single segment after retry; "
                    "leaving it untranslated: %.60s",
                    batch[0] if batch else "",
                )
                return list(batch)
            mid = len(batch) // 2
            logger.info(
                "Retrying a %d-segment batch as %d + %d after a parse/truncation "
                "failure.",
                len(batch),
                mid,
                len(batch) - mid,
            )
            return self._translate_batch(
                batch[:mid], target_lang
            ) + self._translate_batch(batch[mid:], target_lang)

        if len(translated) != len(batch):
            raise TranslationError(
                "Translator returned %d segments for a batch of %d"
                % (len(translated), len(batch))
            )
        return translated


class _Placeholder:
    """An inline element folded into a unit's translated string.

    ``kind`` is ``"opaque"`` for elements restored verbatim (``<img>``,
    ``<br>``, ``<code>``, or inline elements with no translatable text) or
    ``"wrap"`` for inline elements whose inner content is itself translated
    (``<a>``, ``<strong>``, ...). For ``"wrap"`` the placeholder appears as a
    paired tag ``<x-i18n n="K">inner</x-i18n>`` so the model translates the
    inner text as part of the sentence and can reorder it.
    """

    __slots__ = ("kind", "element")

    def __init__(self, kind: str, element: Tag):
        self.kind = kind
        self.element = element


class _TextUnit:
    """One translatable run of phrasing content anchored at a block element.

    ``text`` is the run's inline content flattened into a single string with
    inline elements represented as numbered placeholders. The model translates
    ``text`` freely — moving placeholders wherever the target grammar wants —
    and :meth:`apply` rebuilds the block's children from the translated string.
    """

    def __init__(
        self,
        parent: Tag,
        child_slice: Tuple[int, int],
        text: str,
        placeholders: List[_Placeholder],
        leading_ws: str = "",
        trailing_ws: str = "",
    ):
        self._parent = parent
        self._start, self._end = child_slice
        self.text = text
        self._placeholders = placeholders
        # The run's boundary whitespace, captured from the source and re-applied
        # deterministically so it survives regardless of whether the model
        # preserves leading/trailing whitespace in its JSON string values.
        self._leading_ws = leading_ws
        self._trailing_ws = trailing_ws

    def apply(self, translated: str) -> None:
        """Replace the unit's original children with the translated content."""
        new_nodes = _rebuild_nodes(translated, self._placeholders)
        # Re-apply the source run's leading/trailing whitespace: strip whatever
        # the model returned at the boundaries and restore the original spacing,
        # so adjacent inline runs never collapse together (e.g. "x" + "y" -> "xy").
        new_nodes = _reapply_boundary_whitespace(
            new_nodes, self._leading_ws, self._trailing_ws
        )
        children = list(self._parent.children)
        originals = children[self._start : self._end]
        anchor_index = self._start
        for node in originals:
            node.extract()
        for offset, node in enumerate(new_nodes):
            self._parent.insert(anchor_index + offset, node)


def _is_inline(element: Tag) -> bool:
    """True if the element is phrasing (inline) content folded into a unit."""
    return element.name in _INLINE_TAGS or element.name in _INLINE_OPAQUE_TAGS


def _build_units_for_block(block: Tag) -> List["_TextUnit"]:
    """Build translation units from a block's direct phrasing runs.

    Consecutive text + inline children are grouped into one unit; block-level
    children (which host their own units) act as separators. A run with no
    translatable text yields no unit.
    """
    units: List[_TextUnit] = []
    children = list(block.children)
    run_start: Optional[int] = None

    def _flush(end: int) -> None:
        if run_start is None:
            return
        unit = _make_unit(block, children, run_start, end)
        if unit is not None:
            units.append(unit)

    for index, child in enumerate(children):
        if isinstance(child, NavigableString):
            if isinstance(child, _NON_CONTENT_STRINGS):
                _flush(index)
                run_start = None
                continue
            if run_start is None:
                run_start = index
        elif isinstance(child, Tag) and _is_inline(child):
            if run_start is None:
                run_start = index
        else:
            # Block-level (or skipped) child: it ends the current run and hosts
            # its own units via the outer find_all walk.
            _flush(index)
            run_start = None
    _flush(len(children))
    return units


def _make_unit(
    block: Tag, children: list, start: int, end: int
) -> Optional["_TextUnit"]:
    """Serialize children[start:end] into a placeholder-bearing unit.

    Returns None if the run carries no translatable text (e.g. whitespace or
    only opaque inline elements like a lone ``<br>``).
    """
    placeholders: List[_Placeholder] = []
    text, has_text = _serialize_run(children[start:end], placeholders)
    if not has_text:
        return None
    # Capture the run's boundary whitespace and send only the stripped core to
    # the model; the whitespace is re-applied deterministically on rebuild
    # (apply) so it cannot be lost to model trimming.
    leading_ws = text[: len(text) - len(text.lstrip())]
    trailing_ws = text[len(text.rstrip()):]
    core = text.strip()
    return _TextUnit(
        block, (start, end), core, placeholders, leading_ws, trailing_ws
    )


def _serialize_run(nodes, placeholders: List[_Placeholder]) -> Tuple[str, bool]:
    """Flatten phrasing ``nodes`` into a placeholder string; recurse into inline.

    Appends to ``placeholders`` (a shared flat list for the whole unit) and
    returns ``(serialized_text, has_translatable_text)``.
    """
    parts: List[str] = []
    has_text = False
    for node in nodes:
        if isinstance(node, NavigableString):
            if isinstance(node, _NON_CONTENT_STRINGS):
                continue
            raw = str(node)
            if raw.strip():
                has_text = True
            parts.append(_html_escape(raw))
        elif isinstance(node, Tag):
            idx = len(placeholders)
            if _is_wrappable_inline(node):
                placeholders.append(_Placeholder("wrap", node))
                inner, inner_has = _serialize_run(list(node.children), placeholders)
                has_text = has_text or inner_has
                parts.append(
                    f'<{_PLACEHOLDER_TAG} n="{idx}">{inner}</{_PLACEHOLDER_TAG}>'
                )
            else:
                # Opaque: kept verbatim (code sample, void element, or an inline
                # element carrying no translatable text).
                placeholders.append(_Placeholder("opaque", node))
                parts.append(f'<{_PLACEHOLDER_TAG} n="{idx}"/>')
    return "".join(parts), has_text


def _is_wrappable_inline(element: Tag) -> bool:
    """True if an inline element's inner text should be folded into the run.

    Must be a genuine inline (phrasing) element: a block element nested inside
    an inline one (e.g. HTML5 ``<a><div>...</div></a>``) must NOT be folded, or
    its text would be translated twice — once folded into the ancestor's unit
    and once via its own block unit from the ``find_all`` walk. Such blocks are
    kept as opaque placeholders instead and translated only by their own unit.
    """
    if not _is_inline(element):
        return False
    if element.name in _INLINE_OPAQUE_TAGS or element.name in _SKIP_CONTENT_TAGS:
        return False
    if _element_opts_out(element):
        return False
    return _has_translatable_text(element)


def _has_translatable_text(element: Tag) -> bool:
    """True if the element has descendant text worth translating."""
    for descendant in element.descendants:
        if isinstance(descendant, NavigableString) and not isinstance(
            descendant, _NON_CONTENT_STRINGS
        ):
            if descendant.strip() and not _has_skip_content_ancestor_tag(
                descendant.parent
            ):
                return True
    return False


def _rebuild_nodes(translated: str, placeholders: List[_Placeholder]) -> list:
    """Rebuild BeautifulSoup nodes from a translated unit string.

    Placeholders are matched by their ``n`` index, so reordering across the tag
    boundary is honored. ``wrap`` placeholders are rebuilt as a shell clone of
    the original element (carrying its already-translated attributes) whose
    children come from recursively parsing the placeholder's inner content.
    ``opaque`` placeholders restore the original element verbatim. Any
    placeholder the model dropped is re-appended so content is never lost;
    unexpected model-authored markup is reduced to its text so no foreign
    element is injected into the output.
    """
    fragment = BeautifulSoup(
        f"<{_PLACEHOLDER_TAG}-root>{translated}</{_PLACEHOLDER_TAG}-root>",
        "html.parser",
    )
    root = fragment.find(f"{_PLACEHOLDER_TAG}-root") or fragment
    used: set = set()
    nodes = _emit_nodes(list(root.children), placeholders, used)

    # Re-attach only *opaque* placeholders the model omitted. An opaque
    # placeholder (image, <br>, code sample) carries content that has NO textual
    # representation in the translated stream, so if the model drops its marker
    # the element would vanish — re-attach it to preserve that content.
    #
    # A *wrap* placeholder's translatable text was flattened INTO the sentence,
    # so when the model drops the marker its text is already present in the
    # emitted output; re-attaching the original element would duplicate that
    # text (and re-insert it untranslated). So wrap placeholders are NOT
    # re-attached — at most the inline formatting is lost, never the words.
    for idx, ph in enumerate(placeholders):
        if idx in used:
            continue
        if ph.kind == "opaque":
            nodes.append(ph.element)
        else:
            logger.debug(
                "Model dropped inline marker %d; formatting lost but text "
                "preserved in the translated run.",
                idx,
            )
        used.add(idx)
    return nodes


def _emit_nodes(source_nodes, placeholders: List[_Placeholder], used: set) -> list:
    """Recursively convert parsed placeholder markup back into real nodes."""
    result: list = []
    for node in source_nodes:
        if isinstance(node, NavigableString):
            if not isinstance(node, _NON_CONTENT_STRINGS):
                result.append(NavigableString(str(node)))
        elif isinstance(node, Tag) and node.name == _PLACEHOLDER_TAG:
            idx = _placeholder_index(node)
            if idx is None or not (0 <= idx < len(placeholders)) or idx in used:
                # Unknown, out-of-range, or repeated index: we cannot restore the
                # element, but its inner text is real translated content — emit
                # the children as bare nodes so no words are lost (only the
                # inline formatting of the duplicate/invalid marker is dropped).
                result.extend(_emit_nodes(list(node.children), placeholders, used))
                continue
            used.add(idx)
            ph = placeholders[idx]
            if ph.kind == "opaque":
                result.append(ph.element)
            else:
                shell = _clone_shell(ph.element)
                for child in _emit_nodes(list(node.children), placeholders, used):
                    shell.append(child)
                result.append(shell)
        elif isinstance(node, Tag):
            # Unexpected markup the model invented: keep its text, drop the tag,
            # so no model/attacker-authored element reaches the output.
            text = node.get_text()
            if text:
                result.append(NavigableString(text))
    return result


def _reapply_boundary_whitespace(
    nodes: list, leading_ws: str, trailing_ws: str
) -> list:
    """Restore the run's original leading/trailing whitespace around ``nodes``.

    The model receives the whitespace-stripped core of a run, so its reply has
    no reliable boundary whitespace. This strips whatever the model returned at
    the very start/end and re-glues the source's original whitespace, ensuring
    adjacent inline runs stay separated (e.g. ``<a>x</a> <a>y</a>`` never
    collapses to ``xy``). Leading/trailing NavigableStrings are adjusted in
    place; if the boundary node is an element, a whitespace text node is added.
    """
    if not nodes:
        return [NavigableString(leading_ws + trailing_ws)] if (leading_ws or trailing_ws) else nodes

    if leading_ws:
        first = nodes[0]
        if isinstance(first, NavigableString):
            nodes[0] = NavigableString(leading_ws + str(first).lstrip())
        else:
            nodes.insert(0, NavigableString(leading_ws))

    if trailing_ws:
        last = nodes[-1]
        if isinstance(last, NavigableString):
            nodes[-1] = NavigableString(str(last).rstrip() + trailing_ws)
        else:
            nodes.append(NavigableString(trailing_ws))
    return nodes


def _placeholder_index(node: Tag) -> Optional[int]:
    """Parse the integer ``n`` index off a placeholder tag, or None."""
    try:
        return int(node.get("n", ""))
    except (TypeError, ValueError):
        return None


def _clone_shell(element: Tag) -> Tag:
    """Copy an inline element WITHOUT its children (attributes are preserved).

    Called after attribute translation has mutated the original element in
    place, so the clone carries the translated attributes; its children are
    rebuilt from the translated inner content.
    """
    shell = copy.copy(element)
    shell.clear()
    return shell


def _collect_attr_targets(soup) -> List[Tuple[Tag, str, str]]:
    """Collect (element, attr, value) triples for every translatable attribute.

    Covers global text attributes on any element, ``<input>`` button ``value``
    (submit/button/reset only — never editable field data), and translatable
    ``<meta>`` ``content``. ``translate="no"`` on the element or an ancestor
    opts the element out entirely.
    """
    targets: List[Tuple[Tag, str, str]] = []
    for element in soup.find_all(True):
        if _has_translate_no_self_or_ancestor(element):
            continue
        for attr in _global_translatable_attrs_for(element):
            value = element.get(attr)
            if isinstance(value, str) and value.strip():
                targets.append((element, attr, value))
    return targets


def _global_translatable_attrs_for(element: Tag) -> Tuple[str, ...]:
    """Return the translatable attribute names applicable to ``element``."""
    attrs = list(_GLOBAL_TRANSLATABLE_ATTRS)
    name = element.name
    if name == "input":
        input_type = (element.get("type") or "text").strip().lower()
        if input_type in _BUTTON_INPUT_TYPES:
            attrs.append("value")
    elif name == "meta" and element.get("content"):
        meta_name = (element.get("name") or "").strip().lower()
        meta_prop = (element.get("property") or "").strip().lower()
        if (
            meta_name in _TRANSLATABLE_META_NAMES
            or meta_prop in _TRANSLATABLE_META_PROPERTIES
        ):
            attrs.append("content")
    return tuple(attrs)


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


def _has_skip_content_ancestor_tag(element) -> bool:
    """True if the element sits at/inside a skip-content tag (code/pre/...).

    Walks the full ancestor chain so text nested inside ``<pre>``/``<code>``/
    ``<script>`` via inline wrappers (e.g. a syntax-highlighted
    ``<pre><span>...``) is left untranslated.
    """
    current = element
    while current is not None and getattr(current, "name", None) is not None:
        if current.name in _SKIP_CONTENT_TAGS:
            return True
        current = current.parent
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
            "preserving meaning, tone, and inline formatting markers exactly. "
            "You never add explanations."
        )
        prompt = (
            f"Translate each string in the following JSON array {source_clause}"
            f"into {target_name} ({target_lang}). Rules:\n"
            "- Return ONLY a JSON array of strings, same length and order as the input.\n"
            f"- Some strings contain inline formatting markers <{_PLACEHOLDER_TAG} "
            'n="K"> ... </'
            f"{_PLACEHOLDER_TAG}> (paired) or <{_PLACEHOLDER_TAG} n=\"K\"/> "
            "(standalone). Keep every marker, its `n` value, and its pairing "
            "intact, but MOVE them to wherever the translated word order requires "
            "— translate the text inside a paired marker as part of the sentence.\n"
            "- Do not add, remove, or renumber markers. Do not translate proper "
            "nouns, code, URLs, or numbers.\n"
            "- Keep punctuation and casing natural for the target language.\n\n"
            f"Input:\n{json.dumps(segments, ensure_ascii=False)}"
        )

        # Size the output budget from the input. Translations can be longer than
        # the source (verbose target languages) AND the JSON reply repeats the
        # placeholder markup, and reasoning-capable models (Sonnet 5) spend extra
        # output tokens on a hidden reasoning block. Budget ~3x the input chars
        # (roughly 1 token/char for CJK) plus a large fixed headroom for the
        # reasoning block, capped at the model's ceiling. Undersizing here only
        # costs a retry (adaptive split in _translate_segments), never silent
        # source passthrough.
        input_chars = sum(len(s) for s in segments)
        max_tokens = min(64000, max(8000, input_chars * 3 + 8000))
        raw = client.generate_text(
            prompt=prompt,
            purpose="content_translation",
            system_prompt=system_prompt,
            max_tokens=max_tokens,
        )
        parsed = _parse_translation_array(raw, len(segments))
        if parsed is None:
            # Signal failure so the caller can retry with a smaller batch. A
            # single-segment batch that still fails raises, and the caller
            # decides whether to fall back to source for just that segment.
            raise _BatchParseError(len(segments))
        return parsed

    return _translate


def _parse_translation_array(raw: str, expected: int) -> Optional[List[str]]:
    """Parse the model's JSON array reply, tolerating code fences and prose.

    Returns the parsed list of strings, or ``None`` if a well-formed array of
    the expected length could not be recovered (so the caller can retry with a
    smaller batch rather than silently substituting untranslated source text).

    Parsing starts at the first ``[`` and uses ``raw_decode`` to consume exactly
    one JSON value, so trailing prose the model may append (e.g. ``[...]
    (markers kept)``) is ignored instead of corrupting a last-``]`` slice.
    """
    text = raw.strip()
    start = text.find("[")
    if start == -1:
        logger.warning("No JSON array found in translation reply")
        return None
    try:
        parsed, _end = json.JSONDecoder().raw_decode(text[start:])
    except json.JSONDecodeError as e:
        # Most often a truncated (max_tokens) reply: the array never closes.
        logger.warning("Could not parse translation JSON: %s", e)
        return None
    if not isinstance(parsed, list):
        logger.warning("Translation reply was not a JSON array")
        return None
    result = [str(item) for item in parsed]
    if len(result) != expected:
        # A length mismatch means node alignment is unreliable for the whole
        # batch; signal failure so the caller can re-split rather than guess.
        logger.warning(
            "Translation returned %d items, expected %d", len(result), expected
        )
        return None
    return result
