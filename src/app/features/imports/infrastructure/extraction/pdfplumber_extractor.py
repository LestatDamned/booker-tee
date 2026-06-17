from dataclasses import dataclass
from pathlib import Path

import pdfplumber


@dataclass(frozen=True)
class ExtractedPdfPageTables:
    page_number: int
    tables: list[list[list[str | None]]]


@dataclass(frozen=True)
class ExtractedPdf:
    text_by_page: list[str]
    tables_by_page: list[ExtractedPdfPageTables]
    metadata: dict[str, object]


class PdfPlumberExtractor:
    parser_name = "pdfplumber_raw_extractor"
    parser_version = "0.1"

    def extract(self, file_path: Path) -> ExtractedPdf:
        text_by_page: list[str] = []
        tables_by_page: list[ExtractedPdfPageTables] = []

        with pdfplumber.open(file_path) as pdf:
            metadata = _json_safe_mapping(pdf.metadata or {})
            for page_number, page in enumerate(pdf.pages, start=1):
                text_by_page.append(page.extract_text() or "")
                tables_by_page.append(
                    ExtractedPdfPageTables(
                        page_number=page_number,
                        tables=page.extract_tables() or [],
                    )
                )

        return ExtractedPdf(
            text_by_page=text_by_page,
            tables_by_page=tables_by_page,
            metadata=metadata,
        )


def _json_safe_mapping(raw: dict[str, object]) -> dict[str, object]:
    return {str(key): _json_safe_value(value) for key, value in raw.items()}


def _json_safe_value(value: object) -> object:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    return str(value)
