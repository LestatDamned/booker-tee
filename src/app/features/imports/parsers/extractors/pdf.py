from pathlib import Path

import pdfplumber

from app.features.imports.parsers.extractors.dto import (
    ExtractedStatement,
    ExtractedStatementPageTables,
)
from app.features.imports.parsers.extractors.limits import (
    StatementExtractionLimits,
    StatementResourceLimitError,
)


class PdfPlumberStatementExtractor:
    parser_name = "pdfplumber_raw_extractor"
    parser_version = "0.1"

    def __init__(self, limits: StatementExtractionLimits | None = None) -> None:
        self.limits = limits or StatementExtractionLimits()

    def extract(self, file_path: Path) -> ExtractedStatement:
        text_by_page: list[str] = []
        tables_by_page: list[ExtractedStatementPageTables] = []

        with pdfplumber.open(file_path) as pdf:
            if len(pdf.pages) > self.limits.pdf_max_pages:
                raise StatementResourceLimitError(
                    f"PDF exceeds the {self.limits.pdf_max_pages}-page extraction limit."
                )
            metadata = _json_safe_mapping(pdf.metadata or {})
            character_count = table_count = cell_count = 0
            for page_number, page in enumerate(pdf.pages, start=1):
                page_text = page.extract_text() or ""
                page_tables = page.extract_tables() or []
                next_character_count = character_count + len(page_text)
                next_table_count = table_count + len(page_tables)
                next_cell_count = cell_count + sum(
                    sum(cell is not None for cell in row) for table in page_tables for row in table
                )
                _check_output_limits(
                    self.limits,
                    characters=next_character_count,
                    tables=next_table_count,
                    cells=next_cell_count,
                )
                character_count = next_character_count
                table_count = next_table_count
                cell_count = next_cell_count
                text_by_page.append(page_text)
                tables_by_page.append(
                    ExtractedStatementPageTables(
                        page_number=page_number,
                        tables=page_tables,
                    )
                )

        return ExtractedStatement(
            text_by_page=text_by_page,
            tables_by_page=tables_by_page,
            metadata={
                **metadata,
                "extractor_name": self.parser_name,
                "extractor_version": self.parser_version,
                "source_format": "pdf",
            },
        )


def _check_output_limits(
    limits: StatementExtractionLimits,
    *,
    characters: int,
    tables: int,
    cells: int,
) -> None:
    for value, maximum, name in (
        (characters, limits.pdf_max_characters, "character"),
        (tables, limits.pdf_max_tables, "table"),
        (cells, limits.pdf_max_cells, "cell"),
    ):
        if value > maximum:
            raise StatementResourceLimitError(f"PDF exceeds the {name} extraction limit.")


def _json_safe_mapping(raw: dict[str, object]) -> dict[str, object]:
    return {str(key): _json_safe_value(value) for key, value in raw.items()}


def _json_safe_value(value: object) -> object:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    return str(value)
