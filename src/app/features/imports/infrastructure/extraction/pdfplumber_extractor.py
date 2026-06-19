from pathlib import Path

import pdfplumber

from app.features.imports.infrastructure.extraction.extracted_statement import (
    ExtractedStatement,
    ExtractedStatementPageTables,
)

ExtractedPdfPageTables = ExtractedStatementPageTables
ExtractedPdf = ExtractedStatement


class PdfPlumberExtractor:
    parser_name = "pdfplumber_raw_extractor"
    parser_version = "0.1"

    def extract(self, file_path: Path) -> ExtractedStatement:
        text_by_page: list[str] = []
        tables_by_page: list[ExtractedStatementPageTables] = []

        with pdfplumber.open(file_path) as pdf:
            metadata = _json_safe_mapping(pdf.metadata or {})
            for page_number, page in enumerate(pdf.pages, start=1):
                text_by_page.append(page.extract_text() or "")
                tables_by_page.append(
                    ExtractedStatementPageTables(
                        page_number=page_number,
                        tables=page.extract_tables() or [],
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


def _json_safe_mapping(raw: dict[str, object]) -> dict[str, object]:
    return {str(key): _json_safe_value(value) for key, value in raw.items()}


def _json_safe_value(value: object) -> object:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    return str(value)
