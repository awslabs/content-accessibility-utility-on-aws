# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Offline unit tests for the i18n orchestration API.

The translation model call is injected via the ``translate_fn`` option, so the
full file-I/O orchestration is exercised without AWS access.
"""

import os

import pytest

from content_accessibility_utility_on_aws.i18n.api import (
    translate_html_accessibility,
)
from content_accessibility_utility_on_aws.utils.logging_helper import TranslationError


def _tag(segments, target, source):
    return [f"[{target}]{s}" for s in segments]


SOURCE = (
    '<!DOCTYPE html><html lang="en"><head><title>Doc</title></head>'
    "<body><h1>Report</h1></body></html>"
)


@pytest.fixture
def src_file(tmp_path):
    path = tmp_path / "doc.html"
    path.write_text(SOURCE, encoding="utf-8")
    return str(path)


def test_per_language_output(src_file, tmp_path):
    out_dir = tmp_path / "out"
    result = translate_html_accessibility(
        src_file,
        options={"target_languages": "es,fr", "translate_fn": _tag},
        output_path=str(out_dir),
    )
    assert set(result["target_languages"]) == {"es", "fr"}
    assert os.path.exists(result["output_files"]["es"])
    assert os.path.exists(result["output_files"]["fr"])
    es = open(result["output_files"]["es"], encoding="utf-8").read()
    assert "[es]Report" in es
    assert 'lang="es"' in es


def test_multilingual_output(src_file, tmp_path):
    out_file = tmp_path / "multi.html"
    result = translate_html_accessibility(
        src_file,
        options={
            "target_languages": ["es", "fr"],
            "multilingual": True,
            "translate_fn": _tag,
        },
        output_path=str(out_file),
    )
    assert result["multilingual"] is True
    content = open(result["output_files"]["multilingual"], encoding="utf-8").read()
    assert 'id="i18n-language-select"' in content
    assert "navigator.languages" in content
    # Source language included as a selectable option.
    assert 'data-lang="en"' in content


def test_source_language_autodetected_from_lang_attr(src_file):
    result = translate_html_accessibility(
        src_file,
        options={"target_languages": "es", "translate_fn": _tag},
    )
    assert result["source_language"] == "en"


def test_target_equal_to_source_passes_through(src_file, tmp_path):
    result = translate_html_accessibility(
        src_file,
        options={
            "target_languages": "en",
            "source_language": "en",
            "translate_fn": _tag,
        },
        output_path=str(tmp_path / "out"),
    )
    content = open(result["output_files"]["en"], encoding="utf-8").read()
    # No translation applied when target == source.
    assert "[en]Report" not in content
    assert "Report" in content


def test_missing_target_language_raises(src_file):
    with pytest.raises(TranslationError):
        translate_html_accessibility(src_file, options={"translate_fn": _tag})


def test_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        translate_html_accessibility(
            str(tmp_path / "nope.html"),
            options={"target_languages": "es", "translate_fn": _tag},
        )


def test_directory_input_translates_every_page(tmp_path):
    # Multi-page directory: ALL pages must be translated, not just one.
    d = tmp_path / "html"
    d.mkdir()
    for name in ("page-1.html", "page-2.html", "page-3.html"):
        (d / name).write_text(SOURCE, encoding="utf-8")
    result = translate_html_accessibility(
        str(d),
        options={"target_languages": "es", "translate_fn": _tag},
        output_path=str(tmp_path / "out"),
    )
    of = result["output_files"]
    # Nested per source-file stem for directory input.
    assert set(of) == {"page-1", "page-2", "page-3"}
    for stem in of:
        assert os.path.exists(of[stem]["es"])


def test_multilingual_includes_source_when_detection_fails(tmp_path):
    # No <html lang>, no source_language, langdetect absent -> detection is None.
    # The original content must still be included as a selectable option.
    src = tmp_path / "doc.html"
    src.write_text(
        "<!DOCTYPE html><html><head><title>T</title></head>"
        "<body><h1>Original</h1></body></html>",
        encoding="utf-8",
    )
    result = translate_html_accessibility(
        str(src),
        options={
            "target_languages": "es",
            "source_language": None,
            "multilingual": True,
            "translate_fn": _tag,
        },
        output_path=str(tmp_path / "multi.html"),
    )
    content = open(result["output_files"]["multilingual"], encoding="utf-8").read()
    # The untranslated original survives, labeled with the "undetermined" tag.
    assert "Original" in content
    assert 'data-lang="und"' in content
    assert 'data-lang="es"' in content
