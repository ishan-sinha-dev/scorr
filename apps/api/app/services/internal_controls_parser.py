import csv
import io
from typing import NamedTuple

import openpyxl

_CSV_CONTENT_TYPE = "text/csv"
_XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

DETERMINISTIC_CONTENT_TYPES = frozenset({_CSV_CONTENT_TYPE, _XLSX_CONTENT_TYPE})

_DESCRIPTION_HEADERS = {"description", "control description", "control"}
_CONTROL_ID_HEADERS = {"control id", "id", "control #", "control number"}


class ParsedControl(NamedTuple):
    control_id: str | None
    description: str
    source_row_ref: str


def _match_column(headers: list[str], candidates: set[str]) -> int | None:
    normalized = [header.strip().lower() for header in headers]
    for index, header in enumerate(normalized):
        if header in candidates:
            return index
    return None


def _cell_str(value: object) -> str:
    return "" if value is None else str(value).strip()


def _parse_rows(rows: list[list[object]]) -> list[ParsedControl]:
    if not rows:
        raise ValueError("File has no rows")

    headers = [_cell_str(cell) for cell in rows[0]]
    description_col = _match_column(headers, _DESCRIPTION_HEADERS)
    if description_col is None:
        raise ValueError(
            "No description column found (expected one of: "
            + ", ".join(sorted(_DESCRIPTION_HEADERS))
            + ")"
        )
    control_id_col = _match_column(headers, _CONTROL_ID_HEADERS)

    controls: list[ParsedControl] = []
    # Row 1 is the header; data starts at spreadsheet row 2.
    for sheet_row_number, row in enumerate(rows[1:], start=2):
        description = _cell_str(row[description_col]) if description_col < len(row) else ""
        if not description:
            continue
        control_id = (
            _cell_str(row[control_id_col]) or None
            if control_id_col is not None and control_id_col < len(row)
            else None
        )
        controls.append(
            ParsedControl(
                control_id=control_id,
                description=description,
                source_row_ref=str(sheet_row_number),
            )
        )
    return controls


def parse_csv(content: bytes) -> list[ParsedControl]:
    # utf-8-sig transparently strips a BOM, which Excel-exported CSVs
    # commonly include on the first cell.
    text = content.decode("utf-8-sig")
    rows: list[list[object]] = [list(row) for row in csv.reader(io.StringIO(text))]
    return _parse_rows(rows)


def parse_xlsx(content: bytes) -> list[ParsedControl]:
    # First sheet only — no consumer for multi-sheet handling yet.
    workbook = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    sheet = workbook.worksheets[0]
    rows: list[list[object]] = [list(row) for row in sheet.iter_rows(values_only=True)]
    return _parse_rows(rows)


def parse(content_type: str, content: bytes) -> list[ParsedControl]:
    if content_type == _CSV_CONTENT_TYPE:
        return parse_csv(content)
    if content_type == _XLSX_CONTENT_TYPE:
        return parse_xlsx(content)
    raise ValueError(f"No deterministic parser for content type: {content_type}")
