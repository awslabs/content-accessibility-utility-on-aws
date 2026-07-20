# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Offline unit tests for the HTML translator.

The translation model call is injected (``translate_fn``), so these run without
any AWS access. They assert the structure-preserving contract: markup, scripts,
and opt-out content are untouched while visible text and accessibility
attributes are translated, and language/direction metadata is set correctly.
"""

import pytest

from content_accessibility_utility_on_aws.i18n.translator import (
    HTMLTranslator,
    _parse_translation_array,
)
from content_accessibility_utility_on_aws.utils.logging_helper import TranslationError


def _tag(segments, target, source):
    """Fake translator: prefix each segment with the target language tag."""
    return [f"[{target}]{s}" for s in segments]


SAMPLE = (
    '<!DOCTYPE html><html lang="en"><head><title>Title</title></head>'
    "<body><h1>Welcome</h1><p>A <strong>bold</strong> word.</p>"
    '<img src="a.png" alt="A cat" title="kitty">'
    '<button aria-label="Close">X</button>'
    '<script>var keep="do not translate";</script>'
    '<code>print(1)</code>'
    '<span translate="no">BrandName</span></body></html>'
)


@pytest.fixture
def translator():
    return HTMLTranslator(translate_fn=_tag, source_lang="en")


def test_visible_text_translated(translator):
    out = translator.translate_html(SAMPLE, "es")
    assert "[es]Welcome" in out
    # "bold" is inside <strong>, folded into its paragraph's sentence unit, so
    # the whole run is translated as one segment and the <strong> is preserved.
    assert "[es]" in out and "<strong>bold</strong>" in out


def test_doctype_preserved(translator):
    out = translator.translate_html(SAMPLE, "es")
    assert "<!DOCTYPE html>" in out
    assert "[es]html" not in out.lower()


def test_root_lang_updated(translator):
    out = translator.translate_html(SAMPLE, "fr")
    assert 'lang="fr"' in out


def test_rtl_direction_set():
    out = HTMLTranslator(translate_fn=_tag, source_lang="en").translate_html(SAMPLE, "ar")
    assert 'dir="rtl"' in out


def test_accessibility_attributes_translated(translator):
    out = translator.translate_html(SAMPLE, "es")
    assert 'alt="[es]A cat"' in out
    assert 'title="[es]kitty"' in out
    assert 'aria-label="[es]Close"' in out


def test_script_and_code_untouched(translator):
    out = translator.translate_html(SAMPLE, "es")
    assert 'var keep="do not translate"' in out
    assert "<code>print(1)</code>" in out


def test_translate_no_respected(translator):
    out = translator.translate_html(SAMPLE, "es")
    assert ">BrandName<" in out
    assert "[es]BrandName" not in out


def test_missing_target_raises(translator):
    with pytest.raises(TranslationError):
        translator.translate_html(SAMPLE, "")


def test_batching_covers_all_segments():
    # batch_size of 1 forces many calls; every segment must still be translated.
    tr = HTMLTranslator(translate_fn=_tag, source_lang="en", batch_size=1)
    out = tr.translate_html(SAMPLE, "de")
    assert "[de]Welcome" in out
    # The paragraph (containing <strong>bold</strong>) is its own unit segment.
    assert "[de]" in out and "<strong>bold</strong>" in out


def test_wrong_length_batch_raises():
    def bad(segments, target, source):
        return segments[:-1]  # drop one -> length mismatch

    tr = HTMLTranslator(translate_fn=bad, source_lang="en")
    with pytest.raises(TranslationError):
        tr.translate_html(SAMPLE, "es")


def test_parse_translation_array_plain():
    assert _parse_translation_array('["a", "b"]', 2) == ["a", "b"]


def test_parse_translation_array_code_fence():
    raw = '```json\n["hola", "mundo"]\n```'
    assert _parse_translation_array(raw, 2) == ["hola", "mundo"]


def test_parse_translation_array_trailing_prose_ignored():
    # A valid array followed by prose containing a bracket must still parse
    # (raw_decode consumes exactly the array), not fail on a last-']' slice.
    raw = '["Hola", "Mundo"] (kept placeholder [0] intact)'
    assert _parse_translation_array(raw, 2) == ["Hola", "Mundo"]


def test_parse_translation_array_malformed_returns_none():
    # Unparseable -> None so the caller can split-and-retry (not silent source).
    assert _parse_translation_array("not json at all", 2) is None


def test_parse_translation_array_truncated_returns_none():
    # A truncated (unclosed) array -> None, signalling truncation to the caller.
    assert _parse_translation_array('["Hola", "Mun', 2) is None


def test_parse_translation_array_length_mismatch_returns_none():
    # Wrong count -> None (node alignment unreliable), triggers re-split.
    assert _parse_translation_array('["a"]', 2) is None


def test_nested_code_in_pre_not_translated():
    # Text nested inside <pre> via an inline wrapper must stay verbatim.
    html = '<html><body><pre><span>rm -rf /tmp</span></pre></body></html>'
    out = HTMLTranslator(translate_fn=_tag, source_lang="en").translate_html(html, "es")
    assert "rm -rf /tmp" in out
    assert "[es]rm -rf /tmp" not in out


def test_translate_no_on_container_protects_descendant_attributes():
    # translate="no" on an ancestor must opt out descendant alt/title too.
    html = (
        '<html><body><div translate="no">'
        '<img alt="Acme Home" title="Acme"></div></body></html>'
    )
    out = HTMLTranslator(translate_fn=_tag, source_lang="en").translate_html(html, "es")
    assert 'alt="Acme Home"' in out
    assert 'title="Acme"' in out
    assert "[es]" not in out


def test_translate_to_languages_returns_all():
    tr = HTMLTranslator(translate_fn=_tag, source_lang="en")
    result = tr.translate_to_languages(SAMPLE, ["es", "fr", "de"])
    assert set(result) == {"es", "fr", "de"}
    assert "[es]Welcome" in result["es"]
    assert "[fr]Welcome" in result["fr"]
    assert 'lang="de"' in result["de"]


def test_translate_to_languages_extracts_source_once():
    # The source should be walked/extracted a single time regardless of the
    # number of target languages. Count _collect_targets invocations.
    calls = {"n": 0}
    tr = HTMLTranslator(translate_fn=_tag, source_lang="en")
    original = tr._collect_targets

    def counting(soup):
        calls["n"] += 1
        return original(soup)

    tr._collect_targets = counting
    tr.translate_to_languages(SAMPLE, ["es", "fr", "de"])
    # One extraction for the template + one re-parse per language for
    # reinsertion = 1 + 3. The template extraction (the expensive segment
    # gathering feeding the model) happens exactly once.
    assert calls["n"] == 4


def test_default_translate_fn_reuses_single_client(monkeypatch):
    # The default Bedrock path must build the client at most once across
    # batches/languages, not per call.
    import content_accessibility_utility_on_aws.remediate.services.bedrock_client as bc

    constructed = {"n": 0}

    class FakeClient:
        def __init__(self, *a, **k):
            constructed["n"] += 1

        def generate_text(self, prompt, purpose="general", **kw):
            import json

            arr = json.loads(prompt[prompt.find("Input:\n") + 7 :])
            return json.dumps([f"T-{s}" for s in arr], ensure_ascii=False)

    monkeypatch.setattr(bc, "BedrockClient", FakeClient)
    # batch_size=1 forces multiple batches; multiple languages multiply calls.
    tr = HTMLTranslator(source_lang="en", batch_size=1)
    tr.translate_to_languages(SAMPLE, ["es", "fr"])
    assert constructed["n"] == 1


def test_model_id_and_profile_threaded_to_client(monkeypatch):
    import content_accessibility_utility_on_aws.remediate.services.bedrock_client as bc

    seen = {}

    class FakeClient:
        def __init__(self, model_id=None, profile=None):
            seen["model_id"] = model_id
            seen["profile"] = profile

        def generate_text(self, prompt, purpose="general", **kw):
            import json

            arr = json.loads(prompt[prompt.find("Input:\n") + 7 :])
            return json.dumps(list(arr), ensure_ascii=False)

    monkeypatch.setattr(bc, "BedrockClient", FakeClient)
    tr = HTMLTranslator(source_lang="en", model_id="my-model", profile="my-prof")
    tr.translate_html(SAMPLE, "es")
    assert seen == {"model_id": "my-model", "profile": "my-prof"}


# --- Inline-container translation (word order across tags) -------------------


def _move_placeholder_to_front(segments, target, source):
    """Fake translator that moves a paired/standalone placeholder to the front.

    Simulates a target language whose grammar reorders an inline element across
    the tag boundary, exercising placeholder reordering without corrupting the
    marker itself.
    """
    import re

    pattern = re.compile(r'<x-i18n n="\d+">.*?</x-i18n>|<x-i18n n="\d+"/>')
    out = []
    for seg in segments:
        m = pattern.search(seg)
        if not m:
            out.append(seg)
            continue
        marker = m.group(0)
        rest = (seg[: m.start()] + seg[m.end():]).strip()
        out.append(f"{marker} {rest}")
    return out


def test_sentence_with_inline_link_is_one_unit():
    # "Click <a>here</a> now" must be a single segment so the model can reorder.
    html = '<html><body><p>Click <a href="/x">here</a> now</p></body></html>'
    captured = {}

    def fake(segments, target, source):
        captured["segments"] = list(segments)
        return [f"[{target}]{s}" for s in segments]

    HTMLTranslator(translate_fn=fake, source_lang="en").translate_html(html, "ja")
    # One unit for the whole paragraph, with the link as a paired placeholder.
    assert len(captured["segments"]) == 1
    assert "Click" in captured["segments"][0]
    assert 'n="0"' in captured["segments"][0]
    assert "here" in captured["segments"][0]  # inner text travels with the unit


def test_inline_element_can_be_reordered():
    # A translator that moves the placeholder must move the <a> and keep it valid.
    html = '<html><body><p>alpha <a href="/x">beta</a> gamma</p></body></html>'
    out = HTMLTranslator(
        translate_fn=_move_placeholder_to_front, source_lang="en"
    ).translate_html(html, "ja")
    # The link survives as a real element with its href and inner text intact,
    # now moved to the front of the sentence.
    assert '<a href="/x">beta</a>' in out
    assert out.index('<a href="/x">beta</a>') < out.index("alpha")


def test_inner_link_text_is_translatable():
    # The text inside <a> is part of the sentence unit, so it is translated
    # (here: prefixed) rather than left untouched.
    html = '<html><body><p>See <a href="/x">the docs</a>.</p></body></html>'
    captured = {}

    def fake(segments, target, source):
        captured["segments"] = list(segments)
        return list(segments)

    HTMLTranslator(translate_fn=fake, source_lang="en").translate_html(html, "es")
    assert "the docs" in captured["segments"][0]


def test_dropped_wrap_marker_keeps_text_without_duplication():
    # Realistic model behavior: it drops the paired marker TAGS but keeps the
    # inner text. The text must survive exactly once (not be duplicated by
    # re-attaching the original element), even though the <a> formatting is lost.
    def drop_wrap_tags(segments, target, source):
        import re

        # Remove only the marker tags, keeping inner text (what real models do).
        return [
            re.sub(r'<x-i18n n="\d+">|</x-i18n>', "", s) for s in segments
        ]

    html = '<html><body><p>Read <a href="/x">this</a> now</p></body></html>'
    out = HTMLTranslator(translate_fn=drop_wrap_tags, source_lang="en").translate_html(
        html, "es"
    )
    # "this" appears exactly once (no duplication), and there is no stray
    # untranslated <a> re-appended after the sentence.
    assert out.count("this") == 1
    assert "Read this now" in out


def test_dropped_opaque_marker_reattaches_element():
    # An opaque placeholder (e.g. <img>) has no textual representation, so if the
    # model drops its marker the element MUST be re-attached (content preserved).
    def drop_all_markers(segments, target, source):
        import re

        return [re.sub(r'<x-i18n n="\d+"/>', "", s) for s in segments]

    html = '<html><body><p>See <img src="c.png" alt="chart"> here</p></body></html>'
    out = HTMLTranslator(translate_fn=drop_all_markers, source_lang="en").translate_html(
        html, "es"
    )
    assert '<img' in out and 'src="c.png"' in out


def test_model_injected_markup_is_neutralized():
    # If the model returns unexpected tags (not our placeholders), they must be
    # reduced to text so no foreign element is injected.
    def inject(segments, target, source):
        return ["<script>alert(1)</script>" + s for s in segments]

    html = "<html><body><p>hello</p></body></html>"
    out = HTMLTranslator(translate_fn=inject, source_lang="en").translate_html(
        html, "es"
    )
    assert "<script>alert(1)</script>" not in out
    assert "alert(1)" in out  # kept as text


# --- Expanded attribute coverage --------------------------------------------


def test_submit_input_value_translated():
    html = '<html><body><input type="submit" value="Send"></body></html>'
    out = HTMLTranslator(translate_fn=_tag, source_lang="en").translate_html(html, "es")
    assert 'value="[es]Send"' in out


def test_text_input_value_not_translated():
    # Editable field data must NOT be translated.
    html = '<html><body><input type="text" value="John Doe"></body></html>'
    out = HTMLTranslator(translate_fn=_tag, source_lang="en").translate_html(html, "es")
    assert 'value="John Doe"' in out


def test_meta_description_translated():
    html = (
        '<html><head><meta name="description" content="A page about cats">'
        "</head><body><p>hi</p></body></html>"
    )
    out = HTMLTranslator(translate_fn=_tag, source_lang="en").translate_html(html, "es")
    assert 'content="[es]A page about cats"' in out


def test_meta_generator_not_translated():
    html = (
        '<html><head><meta name="generator" content="SomeTool 1.0">'
        "</head><body><p>hi</p></body></html>"
    )
    out = HTMLTranslator(translate_fn=_tag, source_lang="en").translate_html(html, "es")
    assert 'content="SomeTool 1.0"' in out


def test_og_description_translated():
    html = (
        '<html><head><meta property="og:description" content="Share text">'
        "</head><body><p>hi</p></body></html>"
    )
    out = HTMLTranslator(translate_fn=_tag, source_lang="en").translate_html(html, "es")
    assert 'content="[es]Share text"' in out


# --- Regression: max_tokens sizing for the default Bedrock translator --------


def test_default_translator_sizes_max_tokens_to_input(monkeypatch):
    # A multi-segment batch must request far more than the 2000-token remediation
    # default, or Sonnet 5 truncates the JSON array (stopReason=max_tokens).
    import content_accessibility_utility_on_aws.remediate.services.bedrock_client as bc

    seen = {}

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def generate_text(self, prompt, purpose="general", max_tokens=None, **kw):
            import json

            seen["max_tokens"] = max_tokens
            arr = json.loads(prompt[prompt.find("Input:\n") + 7 :])
            return json.dumps(list(arr), ensure_ascii=False)

    monkeypatch.setattr(bc, "BedrockClient", FakeClient)
    # A long paragraph -> large input -> large max_tokens request.
    big = "word " * 400
    html = f"<html><body><p>{big}</p></body></html>"
    HTMLTranslator(source_lang="en").translate_html(html, "es")
    assert seen["max_tokens"] >= 4000


# --- Regression: fixes from the second code review --------------------------


def test_whitespace_between_inline_elements_preserved():
    # Model trims leading/trailing whitespace of the segment core; the run's
    # boundary/inter-element whitespace must be restored deterministically so
    # adjacent inline runs never collapse together.
    def strip_echo(segments, target, source):
        return [s.strip() for s in segments]

    html = '<html><body><p><a href="/a">x</a> <a href="/b">y</a></p></body></html>'
    out = HTMLTranslator(translate_fn=strip_echo, source_lang="en").translate_html(
        html, "es"
    )
    # There must still be a space between the two links (not "xy").
    assert "</a> <a" in out


def test_block_nested_in_inline_not_double_translated():
    # HTML5 block-level link: <a><div><p>Big</p></div></a>. The <p> text must be
    # sent to the model exactly once, not folded into the <a> run AND collected
    # as its own block unit.
    captured = {}

    def fake(segments, target, source):
        captured.setdefault("all", []).extend(segments)
        return [f"[{target}]{s}" for s in segments]

    html = '<html><body><a href="/x"><div><p>Big</p></div></a></body></html>'
    HTMLTranslator(translate_fn=fake, source_lang="en").translate_html(html, "es")
    # "Big" should appear in exactly one outbound segment, not two.
    segments_with_big = [s for s in captured["all"] if "Big" in s]
    assert len(segments_with_big) == 1, captured["all"]


def test_truncated_batch_splits_and_retries():
    # A translator that fails (raises the internal parse error) on batches larger
    # than 1 must be split down to single segments, each translated, with no
    # whole-batch revert to source.
    from content_accessibility_utility_on_aws.i18n import translator as tr_mod

    calls = {"n": 0}

    def flaky(segments, target, source):
        calls["n"] += 1
        if len(segments) > 1:
            raise tr_mod._BatchParseError(len(segments))
        return [f"[{target}]{s}" for s in segments]

    html = (
        "<html><body>"
        + "".join(f"<p>Para {i}</p>" for i in range(4))
        + "</body></html>"
    )
    out = HTMLTranslator(translate_fn=flaky, source_lang="en", batch_size=4).translate_html(
        html, "es"
    )
    # Every paragraph got translated despite the initial batch failing.
    for i in range(4):
        assert f"[es]Para {i}" in out


def test_single_segment_failure_falls_back_to_source():
    # If even a size-1 batch fails, that ONE segment is left untranslated (not an
    # exception, not a whole-document failure).
    from content_accessibility_utility_on_aws.i18n import translator as tr_mod

    def always_fail(segments, target, source):
        raise tr_mod._BatchParseError(len(segments))

    html = "<html><body><p>Only</p></body></html>"
    out = HTMLTranslator(translate_fn=always_fail, source_lang="en").translate_html(
        html, "es"
    )
    assert "Only" in out  # left as source, no crash
