from app.features.imports.mapping.analysis.dto import (
    TextCandidateTable,
    UnknownStatementAnalysis,
    UnknownStatementStatus,
)
from app.features.imports.mapping.analysis.hints import (
    detect_bank_name_from_hints,
    detect_statement_type_from_hints,
    extract_statement_control_totals,
)
from app.features.imports.mapping.analysis.tables import build_table_previews
from app.features.imports.mapping.analysis.text_tables import (
    build_text_candidate_table_previews,
    build_text_candidate_tables,
)
from app.features.imports.parsers.extractors.dto import ExtractedStatement


class StatementAnalyzer:
    @staticmethod
    def analyze(extracted: ExtractedStatement) -> UnknownStatementAnalysis:
        text = "\n".join(extracted.text_by_page)
        table_previews = build_table_previews(extracted)
        generated_text_tables: list[TextCandidateTable] = []
        if not table_previews:
            generated_text_tables = build_text_candidate_tables(extracted)
            table_previews = build_text_candidate_table_previews(generated_text_tables)
        control_totals = extract_statement_control_totals(extracted.text_by_page)
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
            detected_bank_name=detect_bank_name_from_hints(text),
            detected_statement_type=detect_statement_type_from_hints(text),
            text_based=text_based,
            page_count=len(extracted.text_by_page),
            table_count=sum(len(page.tables) for page in extracted.tables_by_page),
            table_previews=table_previews,
            generated_text_tables=generated_text_tables,
            control_totals=control_totals,
        )


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
