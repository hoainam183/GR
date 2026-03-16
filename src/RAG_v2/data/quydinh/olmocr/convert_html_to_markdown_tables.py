#!/usr/bin/env python3
"""
Script to convert HTML tables to Markdown tables in a Markdown file.
"""

import re
from html.parser import HTMLParser
from typing import List, Dict


class HTMLTableParser(HTMLParser):
    """Parser for HTML table to extract table data."""

    def __init__(self):
        super().__init__()
        self.tables = []
        self.current_table = []
        self.current_row = []
        self.current_cell = []
        self.in_table = False
        self.in_row = False
        self.in_cell = False
        self.cell_type = None  # 'th' or 'td'
        self.cell_attrs = {}

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)

        if tag == "table":
            self.in_table = True
            self.current_table = []

        elif tag == "tr" and self.in_table:
            self.in_row = True
            self.current_row = []

        elif tag in ["th", "td"] and self.in_row:
            self.in_cell = True
            self.cell_type = tag
            self.current_cell = []
            self.cell_attrs = attrs_dict

        elif tag == "br" and self.in_cell:
            self.current_cell.append("<br>")

        elif tag == "b" and self.in_cell:
            self.current_cell.append("**")

    def handle_endtag(self, tag):
        if tag == "table" and self.in_table:
            if self.current_table:
                self.tables.append(self.current_table)
            self.in_table = False
            self.current_table = []

        elif tag == "tr" and self.in_row:
            if self.current_row:
                self.current_table.append(self.current_row)
            self.in_row = False
            self.current_row = []

        elif tag in ["th", "td"] and self.in_cell:
            cell_text = "".join(self.current_cell).strip()
            colspan = int(self.cell_attrs.get("colspan", 1))
            rowspan = int(self.cell_attrs.get("rowspan", 1))

            cell_info = {
                "text": cell_text,
                "type": self.cell_type,
                "colspan": colspan,
                "rowspan": rowspan,
            }
            self.current_row.append(cell_info)

            self.in_cell = False
            self.current_cell = []
            self.cell_attrs = {}

        elif tag == "b" and self.in_cell:
            self.current_cell.append("**")

    def handle_data(self, data):
        if self.in_cell:
            self.current_cell.append(data)


def convert_table_to_markdown(
    table_data: List[List[Dict]],
    fill_rowspan: bool = True,
    fill_empty_from_above: bool = True,
    fill_empty_columns: int = 4,  # Number of leading columns to fill empty cells from above
) -> str:
    """Convert parsed HTML table data to Markdown format with proper rowspan/colspan handling.

    Args:
        table_data: Parsed table data from HTMLTableParser
        fill_rowspan: If True, repeat the cell value for all spanned rows (better for readability).
                     If False, leave spanned cells empty (original behavior).
        fill_empty_from_above: If True, fill empty cells in leading columns with value from row above.
        fill_empty_columns: Number of leading columns to apply fill_empty_from_above logic.
    """

    if not table_data:
        return ""

    # Calculate max columns by considering both colspan and the actual grid structure
    max_cols = 0
    for row in table_data:
        col_count = sum(cell["colspan"] for cell in row)
        max_cols = max(max_cols, col_count)

    # Create a grid to handle rowspan and colspan
    # Each cell will store: {"text": str, "type": str, "is_spanned": bool, "original_text": str}
    grid = []
    num_rows = len(table_data) + 10  # Add extra rows for safety with rowspan
    for _ in range(num_rows):
        grid.append([None] * max_cols)

    # Track which cells are spanned (for rowspan fill)
    rowspan_sources = {}  # (row, col) -> original text

    # Fill the grid with cell data
    for row_idx, row in enumerate(table_data):
        col_idx = 0
        for cell in row:
            # Find next available column
            while col_idx < max_cols and grid[row_idx][col_idx] is not None:
                col_idx += 1

            if col_idx >= max_cols:
                break

            # Fill cells according to colspan and rowspan
            for r in range(cell["rowspan"]):
                for c in range(cell["colspan"]):
                    target_row = row_idx + r
                    target_col = col_idx + c

                    if target_row < num_rows and target_col < max_cols:
                        if r == 0 and c == 0:
                            # Original cell
                            grid[target_row][target_col] = {
                                "text": cell["text"],
                                "type": cell["type"],
                                "is_spanned": False,
                                "original_text": cell["text"],
                            }
                        else:
                            # Spanned cell - fill with original text if fill_rowspan is True
                            if fill_rowspan:
                                grid[target_row][target_col] = {
                                    "text": cell[
                                        "text"
                                    ],  # Repeat the original text
                                    "type": cell["type"],
                                    "is_spanned": True,
                                    "original_text": cell["text"],
                                }
                            else:
                                grid[target_row][target_col] = {
                                    "text": "",  # Leave empty for spanned cells
                                    "type": cell["type"],
                                    "is_spanned": True,
                                    "original_text": cell["text"],
                                }

            col_idx += cell["colspan"]

    # Trim grid to actual rows used
    actual_rows = len(table_data)
    grid = grid[:actual_rows]

    # Fill any remaining None cells with empty strings
    for row_idx in range(len(grid)):
        for col_idx in range(len(grid[row_idx])):
            if grid[row_idx][col_idx] is None:
                grid[row_idx][col_idx] = {
                    "text": "",
                    "type": "td",
                    "is_spanned": False,
                    "original_text": "",
                }

    # Fill empty cells from the row above (for columns like CEFR, PEIC that may not have rowspan in HTML)
    # This helps with tables where rowspan was not properly set in the source HTML
    if fill_empty_from_above:
        for row_idx in range(1, len(grid)):  # Start from row 1 (skip header)
            for col_idx in range(min(fill_empty_columns, len(grid[row_idx]))):
                cell = grid[row_idx][col_idx]
                # If cell is empty and not a header cell
                if cell["text"] == "" and cell["type"] == "td":
                    # Get value from the row above
                    above_cell = grid[row_idx - 1][col_idx]
                    if above_cell["text"]:
                        grid[row_idx][col_idx] = {
                            "text": above_cell["text"],
                            "type": cell["type"],
                            "is_spanned": True,  # Mark as filled from above
                            "original_text": above_cell["text"],
                        }

    # Determine header row count
    # Strategy: Look at original table_data to count header rows
    # A row is header if ALL its original cells (before rowspan fill) are 'th' type
    header_row_count = 0
    for row_idx, row in enumerate(table_data):
        if all(cell["type"] == "th" for cell in row):
            header_row_count = row_idx + 1
        else:
            break

    if header_row_count == 0:
        header_row_count = 1

    # If every row is a header row (all <th>), treat only the first row as header
    # so the remaining rows are not silently dropped as "data rows"
    if header_row_count >= len(grid):
        header_row_count = 1

    # Build Markdown table
    md_lines = []

    # For multi-row headers, we need to flatten them into a single row
    # Combine all header rows into one by joining non-empty values
    if header_row_count > 1:
        # First, build a map of parent headers for columns that have colspan > 1
        # This maps column index to parent header text
        parent_headers = {}
        first_col_of_colspan = {}  # Map first column of colspan -> parent text

        # Process the first header row to find parent headers with colspan
        col_idx = 0
        for cell in table_data[0]:
            if cell["colspan"] > 1:
                # Mark the first column of this colspan
                first_col_of_colspan[col_idx] = cell["text"]
                # This is a parent header spanning multiple columns
                # Map all sub-columns to parent
                for c in range(cell["colspan"]):
                    parent_headers[col_idx + c] = cell["text"]
            col_idx += cell["colspan"]

        # Create combined header
        combined_header = [""] * max_cols
        header_filled = [
            False
        ] * max_cols  # Track which columns have been filled with final value

        # Process header rows
        for row_idx in range(header_row_count):
            for col_idx in range(max_cols):
                cell = grid[row_idx][col_idx]
                cell_text = cell["text"]
                is_spanned = cell.get("is_spanned", False)

                # Skip if already filled with final value
                if header_filled[col_idx]:
                    continue

                # Check if this column has a parent header (from colspan)
                parent = parent_headers.get(col_idx, "")
                is_first_of_colspan = col_idx in first_col_of_colspan

                if row_idx == 0 and is_first_of_colspan:
                    # This is the first column of a colspan in row 0
                    # Don't fill yet, wait for sub-header from row 1
                    continue

                if cell_text and not is_spanned:
                    if parent:
                        # This is a sub-header under a parent - use "parent subheader" format
                        combined_header[col_idx] = parent + " " + cell_text
                    else:
                        # No parent, just use the cell text
                        combined_header[col_idx] = cell_text
                    header_filled[col_idx] = True
                elif cell_text and is_spanned and not parent:
                    # This is a rowspan cell (like "Bậc cơ sở" spanning row 0 and 1)
                    # Only set if no parent and not yet filled
                    combined_header[col_idx] = cell_text
                    header_filled[col_idx] = True

        header_row = "| " + " | ".join(combined_header) + " |"
        md_lines.append(header_row)
    else:
        # Single header row
        row_text = "| " + " | ".join(cell["text"] for cell in grid[0]) + " |"
        md_lines.append(row_text)

    # Add separator
    separator = "|" + "|".join(["---"] * max_cols) + "|"
    md_lines.append(separator)

    # Add data rows
    for row_idx in range(header_row_count, len(grid)):
        row_text = (
            "| " + " | ".join(cell["text"] for cell in grid[row_idx]) + " |"
        )
        md_lines.append(row_text)

    return "\n".join(md_lines)


def convert_html_tables_in_file(input_file: str, output_file: str = None):
    """Convert all HTML tables in a Markdown file to Markdown tables."""

    if output_file is None:
        output_file = input_file

    # Read the input file
    with open(input_file, "r", encoding="utf-8") as f:
        content = f.read()

    # Find all table blocks
    table_pattern = re.compile(r"<table>.*?</table>", re.DOTALL | re.IGNORECASE)
    tables_html = table_pattern.findall(content)

    print(f"Found {len(tables_html)} HTML tables")

    # Parse each table and convert to Markdown
    for i, table_html in enumerate(tables_html):
        print(f"\nProcessing table {i + 1}...")

        parser = HTMLTableParser()
        parser.feed(table_html)

        if parser.tables:
            table_data = parser.tables[0]
            markdown_table = convert_table_to_markdown(table_data)

            # Replace HTML table with Markdown table
            content = content.replace(table_html, markdown_table, 1)
            print(f"Converted table {i + 1}")
        else:
            print(f"Warning: Could not parse table {i + 1}")

    # Write the output file
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"\nConversion complete! Output saved to: {output_file}")
    print(f"Total tables converted: {len(tables_html)}")


def main():
    import sys

    if len(sys.argv) < 2:
        print(
            "Usage: python convert_html_to_markdown_tables.py <input_file> [output_file]"
        )
        print("\nExample:")
        print("  python convert_html_to_markdown_tables.py document.md")
        print(
            "  python convert_html_to_markdown_tables.py document.md output.md"
        )
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None

    convert_html_tables_in_file(input_file, output_file)


if __name__ == "__main__":
    main()
