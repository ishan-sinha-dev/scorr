import io

import openpyxl
import pytest

from app.services.internal_controls_parser import ParsedControl, parse, parse_csv, parse_xlsx


def test_parse_csv_happy_path() -> None:
    content = (
        b"Control ID,Description\n"
        b"CC1.1,Management establishes structure\n"
        b",No control id here\n"
        b"CC1.2,\n"  # blank description -> skipped
    ).replace(b"\n", b"\r\n")

    controls = parse_csv(content)

    assert controls == [
        ParsedControl(
            control_id="CC1.1",
            description="Management establishes structure",
            source_row_ref="2",
        ),
        ParsedControl(
            control_id=None, description="No control id here", source_row_ref="3"
        ),
    ]


def test_parse_csv_matches_header_synonyms_case_insensitively() -> None:
    content = b"control,id\nEncrypts data at rest,CC6.1\n"
    controls = parse_csv(content)
    assert controls == [
        ParsedControl(
            control_id="CC6.1", description="Encrypts data at rest", source_row_ref="2"
        )
    ]


def test_parse_csv_raises_when_no_description_column() -> None:
    content = b"foo,bar\n1,2\n"
    with pytest.raises(ValueError, match="No description column found"):
        parse_csv(content)


def _build_xlsx(rows: list[list[object]]) -> bytes:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    for row in rows:
        sheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def test_parse_xlsx_happy_path() -> None:
    content = _build_xlsx(
        [
            ["Description", "Control #"],
            ["Reviews access quarterly", "CC6.2"],
            [None, "CC6.3"],  # blank description -> skipped
        ]
    )

    controls = parse_xlsx(content)

    assert controls == [
        ParsedControl(
            control_id="CC6.2", description="Reviews access quarterly", source_row_ref="2"
        )
    ]


def test_parse_xlsx_raises_when_no_description_column() -> None:
    content = _build_xlsx([["foo", "bar"], [1, 2]])
    with pytest.raises(ValueError, match="No description column found"):
        parse_xlsx(content)


def test_parse_dispatches_by_content_type() -> None:
    csv_content = b"description\nSomething\n"
    assert parse("text/csv", csv_content) == [
        ParsedControl(control_id=None, description="Something", source_row_ref="2")
    ]


def test_parse_raises_for_unknown_content_type() -> None:
    with pytest.raises(ValueError, match="No deterministic parser"):
        parse("application/pdf", b"")
