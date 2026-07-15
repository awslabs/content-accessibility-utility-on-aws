# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Offline regression tests for deterministic table remediation correctness.

These lock in the fixes for the two defects the AI-quality tier surfaced:
1. scope mis-assignment on the top-left corner header, and
2. scrambled ``headers=`` references (row/column index misalignment).

They run without AWS — the fallback (no-client) path assigns scope purely by
position, and header-id linkage is fully deterministic.
"""

from bs4 import BeautifulSoup

from content_accessibility_utility_on_aws.remediate.remediation_strategies.table_remediation import (
    infer_scope_with_confidence,
    remediate_table_headers_id,
    remediate_table_missing_scope,
)

# Region | Q1 Sales | Q2 Sales  (column headers)
# North  | 100      | 120       (North/South are row headers)
# South  | 90       | 95
MATRIX_TABLE = (
    "<table>"
    "<tr><th>Region</th><th>Q1 Sales</th><th>Q2 Sales</th></tr>"
    "<tr><th>North</th><td>100</td><td>120</td></tr>"
    "<tr><th>South</th><td>90</td><td>95</td></tr>"
    "</table>"
)


def _issue():
    return {"type": "table-missing-scope", "location": {"path": "table"}, "element": "table"}


def test_corner_header_is_column_scope():
    # The top-left corner header ("Region") is a column header by convention,
    # even though the first column also holds row headers.
    soup = BeautifulSoup(MATRIX_TABLE, "html.parser")
    remediate_table_missing_scope(soup, _issue())
    scopes = {th.get_text(strip=True): th.get("scope") for th in soup.find_all("th")}
    assert scopes["Region"] == "col"
    assert scopes["Q1 Sales"] == "col"
    assert scopes["Q2 Sales"] == "col"
    assert scopes["North"] == "row"
    assert scopes["South"] == "row"


def test_infer_scope_confidence_flags():
    soup = BeautifulSoup(MATRIX_TABLE, "html.parser")
    ths = {th.get_text(strip=True): th for th in soup.find_all("th")}
    table = soup.find("table")
    # First-row and first-column headers are unambiguous (confident=True).
    assert infer_scope_with_confidence(table, ths["Region"]) == ("col", True)
    assert infer_scope_with_confidence(table, ths["North"]) == ("row", True)


def test_headers_reference_correct_row_and_column():
    soup = BeautifulSoup(MATRIX_TABLE, "html.parser")
    remediate_table_headers_id(
        soup,
        {"type": "table-missing-headers-id", "location": {"path": "table"}, "element": "table"},
    )
    ids = {th.get_text(strip=True): th.get("id") for th in soup.find_all("th")}

    def headers_of(cell_text):
        td = soup.find("td", string=cell_text)
        return set((td.get("headers") or "").split())

    # Cell 100 is in the Q1 column and the North row.
    assert headers_of("100") == {ids["Q1 Sales"], ids["North"]}
    # Cell 95 is in the Q2 column and the South row.
    assert headers_of("95") == {ids["Q2 Sales"], ids["South"]}
    # No data cell references an unrelated header (the scrambling bug).
    assert headers_of("120") == {ids["Q2 Sales"], ids["North"]}
    assert headers_of("90") == {ids["Q1 Sales"], ids["South"]}


def test_headers_ids_are_unique():
    soup = BeautifulSoup(MATRIX_TABLE, "html.parser")
    remediate_table_headers_id(
        soup,
        {"type": "table-missing-headers-id", "location": {"path": "table"}, "element": "table"},
    )
    ids = [th.get("id") for th in soup.find_all("th")]
    assert all(ids)
    assert len(ids) == len(set(ids)), "header ids must be unique"
