# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Table-related accessibility checks.

This module provides checks for proper table accessibility.
"""

from bs4 import Tag

from content_accessibility_utility_on_aws.audit.base_check import AccessibilityCheck


class TableHeaderCheck(AccessibilityCheck):
    """Check for proper table headers (WCAG 1.3.1)."""

    def check(self) -> None:
        """
        Check if tables have proper headers.

        Issues:
            - table-missing-headers: When a data table has no header cells
            - table-missing-scope: When table headers don't have scope attributes
            - table-missing-caption: When a complex table has no caption
        """
        tables = self.soup.find_all("table")

        for table in tables:
            # Skip tables that appear to be for layout
            if self._is_layout_table(table):
                continue

            # Check for headers
            headers = table.find_all("th")
            if not headers:
                self.add_issue(
                    "table-missing-headers",
                    "1.3.1",
                    "major",
                    element=table,
                    description="Data table has no header cells (th elements)",
                )
            else:
                # Check for scope attributes on headers
                for header in headers:
                    if not header.has_attr("scope"):
                        self.add_issue(
                            "table-missing-scope",
                            "1.3.1",
                            "minor",
                            element=header,
                            description="Table header missing scope attribute",
                        )

            # Check for caption
            if self._is_complex_table(table) and not table.find("caption"):
                self.add_issue(
                    "table-missing-caption",
                    "1.3.1",
                    "minor",
                    element=table,
                    description="Complex table missing caption element",
                )

    def _is_layout_table(self, table: Tag) -> bool:
        """
        Determine if a table is likely used for layout rather than data.

        Args:
            table: The table element to check

        Returns:
            True if the table appears to be for layout, False otherwise
        """
        # Check for role="presentation"
        if table.get("role") == "presentation":
            return True

        # Check for CSS classes that suggest layout tables
        css_classes = table.get("class", [])
        layout_class_patterns = ["layout", "grid", "non-data"]
        if any(
            pattern in " ".join(css_classes).lower()
            for pattern in layout_class_patterns
        ):
            return True

        # Check for absence of th elements and caption
        if not table.find("th") and not table.find("caption"):
            # If it has very few cells, it's likely a layout table
            rows = table.find_all("tr")
            if len(rows) <= 1:
                return True

            # Count cells in first row
            first_row_cells = rows[0].find_all(["td", "th"]) if rows else []
            if len(first_row_cells) <= 1:
                return True

        return False

    def _is_complex_table(self, table: Tag) -> bool:
        """
        Determine if a table is complex (needs additional accessibility features).

        Args:
            table: The table element to check

        Returns:
            True if the table appears to be complex, False otherwise
        """
        # Check for merged cells (rowspan or colspan)
        cells = table.find_all(["td", "th"])
        for cell in cells:
            if cell.has_attr("rowspan") and int(cell["rowspan"]) > 1:
                return True
            if cell.has_attr("colspan") and int(cell["colspan"]) > 1:
                return True

        # Check for multiple header rows or columns
        header_rows = [row for row in table.find_all("tr") if row.find("th")]
        if len(header_rows) > 1:
            return True

        # Check for many rows (large tables benefit from captions)
        rows = table.find_all("tr")
        if len(rows) > 10:
            return True

        return False


class TableStructureCheck(AccessibilityCheck):
    """Check for proper table structure (WCAG 1.3.1)."""

    def check(self) -> None:
        """
        Check if tables have proper structure.

        Issues:
            - table-missing-thead: When a table with headers doesn't use thead
            - table-missing-tbody: When a table doesn't use tbody
            - table-missing-headers-id: When a complex table doesn't use headers/id attributes
            - table-irregular-headers: When a table has irregular header structure
        """
        tables = self.soup.find_all("table")

        for table in tables:
            # Skip tables that appear to be for layout
            if self._is_layout_table(table):
                continue

            # Check for thead when there are headers in the first row
            first_row = table.find("tr")
            if first_row and first_row.find("th") and not table.find("thead"):
                self.add_issue(
                    "table-missing-thead",
                    "1.3.1",
                    "minor",
                    element=table,
                    description="Table with headers should use thead element",
                )

            # Check for tbody
            if not table.find("tbody") and len(table.find_all("tr")) > 1:
                self.add_issue(
                    "table-missing-tbody",
                    "1.3.1",
                    "minor",
                    element=table,
                    description="Table should use tbody element",
                )

            # Check for headers/id attributes in complex tables
            if self._is_complex_table(table):
                # Check if any cells use headers attribute
                cells_with_headers = table.find_all("td", attrs={"headers": True})
                headers_with_id = table.find_all("th", attrs={"id": True})

                if not cells_with_headers and not headers_with_id:
                    self.add_issue(
                        "table-missing-headers-id",
                        "1.3.1",
                        "major",
                        element=table,
                        description="Complex table should use headers/id "
                        + "attributes for cell associations",
                    )

            # Check for irregular header structure
            self._check_irregular_headers(table)

    def _is_layout_table(self, table: Tag) -> bool:
        """
        Determine if a table is likely used for layout rather than data.

        Args:
            table: The table element to check

        Returns:
            True if the table appears to be for layout, False otherwise
        """
        # Check for role="presentation"
        if table.get("role") == "presentation":
            return True

        # Check for CSS classes that suggest layout tables
        css_classes = table.get("class", [])
        layout_class_patterns = ["layout", "grid", "non-data"]
        if any(
            pattern in " ".join(css_classes).lower()
            for pattern in layout_class_patterns
        ):
            return True

        # Check for absence of th elements and caption
        if not table.find("th") and not table.find("caption"):
            # If it has very few cells, it's likely a layout table
            rows = table.find_all("tr")
            if len(rows) <= 1:
                return True

            # Count cells in first row
            first_row_cells = rows[0].find_all(["td", "th"]) if rows else []
            if len(first_row_cells) <= 1:
                return True

        return False

    def _is_complex_table(self, table: Tag) -> bool:
        """
        Determine if a table is complex (needs additional accessibility features).

        Args:
            table: The table element to check

        Returns:
            True if the table appears to be complex, False otherwise
        """
        # Check for merged cells (rowspan or colspan)
        cells = table.find_all(["td", "th"])
        for cell in cells:
            if cell.has_attr("rowspan") and int(cell["rowspan"]) > 1:
                return True
            if cell.has_attr("colspan") and int(cell["colspan"]) > 1:
                return True

        # Check for multiple header rows or columns
        header_rows = [row for row in table.find_all("tr") if row.find("th")]
        if len(header_rows) > 1:
            return True

        # Check for many rows (large tables benefit from captions)
        rows = table.find_all("tr")
        if len(rows) > 10:
            return True

        return False

    def _check_irregular_headers(self, table: Tag) -> None:
        """
        Check for irregular header structure in a table.

        Args:
            table: The table element to check
        """
        rows = table.find_all("tr")

        # Skip tables with fewer than 2 rows
        if len(rows) < 2:
            return

        # Check if headers are consistently in the first row or first column
        first_row = rows[0]
        first_row_cells = first_row.find_all(["td", "th"])
        first_row_headers = len(first_row.find_all("th"))

        # Count row headers (th in first cell position, excluding the header row)
        # Only count data rows (rows after the first if first row is all headers)
        first_row_all_headers = first_row_headers == len(first_row_cells)

        # Get cells for each row's first position
        first_col_cells = []
        for row in rows:
            cells = row.find_all(["td", "th"])
            if cells:
                first_col_cells.append(cells[0])

        # Count how many rows have th in first column (excluding header row if it's all th)
        data_rows_start = 1 if first_row_all_headers else 0
        first_col_headers_in_data = sum(
            1 for cell in first_col_cells[data_rows_start:] if cell.name == "th"
        )
        total_data_rows = len(first_col_cells) - data_rows_start

        # If we have some headers but they're not consistently in first row
        # (mixed th/td in the first row)
        if first_row_headers > 0 and first_row_headers < len(first_row_cells):
            self.add_issue(
                "table-irregular-headers",
                "1.3.1",
                "major",
                element=table,
                description="Table has irregular header structure in the first row",
            )

        # If we have SOME row headers in data rows but not ALL data rows have them
        # This catches tables that have inconsistent row header usage
        # (some data rows have th in first column, others don't)
        if first_col_headers_in_data > 0 and first_col_headers_in_data < total_data_rows:
            self.add_issue(
                "table-irregular-headers",
                "1.3.1",
                "major",
                element=table,
                description="Table has irregular header structure in the first column",
            )
