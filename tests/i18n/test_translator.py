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
    assert "[es]bold" in out


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
    assert "[de]bold" in out


def test_wrong_length_batch_raises():
    def bad(segments, target, source):
        return segments[:-1]  # drop one -> length mismatch

    tr = HTMLTranslator(translate_fn=bad, source_lang="en")
    with pytest.raises(TranslationError):
        tr.translate_html(SAMPLE, "es")


def test_parse_translation_array_plain():
    assert _parse_translation_array('["a", "b"]', 2, ["x", "y"]) == ["a", "b"]


def test_parse_translation_array_code_fence():
    raw = '```json\n["hola", "mundo"]\n```'
    assert _parse_translation_array(raw, 2, ["x", "y"]) == ["hola", "mundo"]


def test_parse_translation_array_malformed_falls_back():
    # Unparseable -> return originals so the batch degrades to untranslated text.
    assert _parse_translation_array("not json at all", 2, ["x", "y"]) == ["x", "y"]


def test_parse_translation_array_length_mismatch_padded():
    # Model returned fewer items than expected -> pad with originals.
    assert _parse_translation_array('["a"]', 2, ["x", "y"]) == ["a", "y"]


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
