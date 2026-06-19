from dataclasses import dataclass


@dataclass(frozen=True)
class ExtractedStatementPageTables:
    page_number: int
    tables: list[list[list[str | None]]]


@dataclass(frozen=True)
class ExtractedStatement:
    text_by_page: list[str]
    tables_by_page: list[ExtractedStatementPageTables]
    metadata: dict[str, object]


ExtractedPdfPageTables = ExtractedStatementPageTables
ExtractedPdf = ExtractedStatement
