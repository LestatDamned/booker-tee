from app.features.imports.application.unknown_statements.analysis_dto import (
    UnknownStatementAnalysis,
    UnknownStatementStatus,
)
from app.features.imports.application.unknown_statements.control_totals import (
    extract_unknown_statement_control_totals,
)
from app.features.imports.application.unknown_statements.hints import (
    detect_bank_name_from_hints,
    detect_statement_type_from_hints,
)
from app.features.imports.application.unknown_statements.table_analysis import (
    build_table_previews,
)
from app.features.imports.application.unknown_statements.text_tables import (
    build_text_candidate_table_previews,
)
from app.features.imports.infrastructure.extraction.pdfplumber_extractor import ExtractedPdf


def analyze_unknown_statement(extracted: ExtractedPdf) -> UnknownStatementAnalysis:
    text = "\n".join(extracted.text_by_page)
    table_previews = build_table_previews(extracted)
    if not table_previews:
        table_previews = build_text_candidate_table_previews(extracted)
    control_totals = extract_unknown_statement_control_totals(extracted.text_by_page)
    text_based = any(page.strip() for page in extracted.text_by_page)
    return UnknownStatementAnalysis(
        status=UnknownStatementStatus.NEEDS_MAPPING,
        message=unknown_statement_message(
            text_based=text_based,
            has_table_previews=bool(table_previews),
            has_pdf_table_previews=any(
                preview.source_type == "pdf_table" for preview in table_previews
            ),
        ),
        detected_bank_name=detect_bank_name(text),
        detected_statement_type=detect_statement_type(text),
        text_based=text_based,
        page_count=len(extracted.text_by_page),
        table_count=sum(len(page.tables) for page in extracted.tables_by_page),
        table_previews=table_previews,
        control_totals=control_totals,
    )


def detect_bank_name(text: str) -> str | None:
    return detect_bank_name_from_hints(text)


def detect_statement_type(text: str) -> str | None:
    return detect_statement_type_from_hints(text)


def unknown_statement_message(
    *,
    text_based: bool,
    has_table_previews: bool,
    has_pdf_table_previews: bool,
) -> str:
    if has_pdf_table_previews:
        return (
            "Parser is not available for this statement yet, but transaction-like tables "
            "were extracted. Configure column mapping to import it."
        )
    if has_table_previews:
        return (
            "Parser is not available for this statement yet. No transaction table was "
            "detected, but transaction-like text lines were converted into a reviewable "
            "table. Check the mapping before importing."
        )
    if text_based:
        return (
            "Parser is not available for this statement yet. Text was extracted, but no "
            "transaction table or transaction-like text lines were detected."
        )
    return (
        "Parser is not available for this statement yet, and no readable text was "
        "extracted. OCR may be required before import."
    )
