from dataclasses import dataclass
from uuid import UUID

from app.features.imports.infrastructure.extraction.extracted_statement import ExtractedStatement
from app.features.imports.models import ParseAttempt, UploadedDocument


@dataclass(frozen=True)
class StatementImportContext:
    document: UploadedDocument
    attempt: ParseAttempt
    extracted: ExtractedStatement
    currency: str
    exclude_duplicate_document_id: UUID | None
    supersede_existing_rows: bool


def raw_tables_from_extracted(extracted: ExtractedStatement) -> list[dict[str, object]]:
    return [
        {"page_number": page_tables.page_number, "tables": page_tables.tables}
        for page_tables in extracted.tables_by_page
    ]
