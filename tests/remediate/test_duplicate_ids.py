# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Tests for remediate_duplicate_ids (#4): duplicate ids break label[for]/aria
references, so a shared id resolves only to the first match and a label can name
the wrong control. The deterministic pass makes ids unique and repairs adjacent
label associations.
"""

from bs4 import BeautifulSoup

from content_accessibility_utility_on_aws.remediate.remediation_strategies.form_remediation import (
    remediate_duplicate_ids,
)


def _issue():
    return {"type": "duplicate-id", "location": {"path": "body"}, "element": ""}


def test_dedup_repairs_label_association():
    # The exact dashboard-fixture failure: two id="checkbox-1" with shared labels.
    html = (
        "<html><body>"
        '<div><label for="checkbox-1">Show deltas</label>'
        '<input id="checkbox-1" type="checkbox"></div>'
        '<div><label for="checkbox-1">Auto-refresh</label>'
        '<input id="checkbox-1" type="checkbox"></div>'
        "</body></html>"
    )
    soup = BeautifulSoup(html, "html.parser")
    msg = remediate_duplicate_ids(soup, _issue())
    assert "unique" in msg

    inputs = soup.find_all("input")
    labels = soup.find_all("label")
    ids = [i.get("id") for i in inputs]
    assert len(ids) == len(set(ids))  # all unique now
    # Each label points at its adjacent control.
    assert labels[0].get("for") == inputs[0].get("id")
    assert labels[1].get("for") == inputs[1].get("id")


def test_dedup_is_idempotent():
    html = (
        "<html><body>"
        '<input id="x"><input id="x"><input id="x">'
        "</body></html>"
    )
    soup = BeautifulSoup(html, "html.parser")
    first = remediate_duplicate_ids(soup, _issue())
    assert "2" in first  # two duplicates renamed
    ids = [i.get("id") for i in soup.find_all("input")]
    assert ids == ["x", "x-2", "x-3"]
    second = remediate_duplicate_ids(soup, _issue())
    assert "No duplicate" in second


def test_dedup_avoids_existing_ids():
    # A collision rename must not land on an id already used elsewhere.
    html = (
        "<html><body>"
        '<input id="x"><input id="x"><input id="x-2">'
        "</body></html>"
    )
    soup = BeautifulSoup(html, "html.parser")
    remediate_duplicate_ids(soup, _issue())
    ids = [i.get("id") for i in soup.find_all("input")]
    assert len(ids) == len(set(ids))
    assert "x-2" in ids  # the pre-existing one is untouched
    # The duplicate got x-3 (skipping the taken x-2).
    assert "x-3" in ids


def test_dedup_noop_when_all_unique():
    html = '<html><body><input id="a"><input id="b"></body></html>'
    soup = BeautifulSoup(html, "html.parser")
    assert "No duplicate" in remediate_duplicate_ids(soup, _issue())


def test_dedup_does_not_move_first_occurrence_label():
    # The label for the FIRST occurrence must stay pointing at the first control.
    html = (
        "<html><body>"
        '<label for="d">First</label><input id="d">'
        '<label for="d">Second</label><input id="d">'
        "</body></html>"
    )
    soup = BeautifulSoup(html, "html.parser")
    remediate_duplicate_ids(soup, _issue())
    inputs = soup.find_all("input")
    labels = soup.find_all("label")
    assert labels[0].get("for") == inputs[0].get("id") == "d"
    assert labels[1].get("for") == inputs[1].get("id") != "d"
