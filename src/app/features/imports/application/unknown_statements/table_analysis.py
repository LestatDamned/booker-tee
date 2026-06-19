from app.features.imports.application.unknown_statements.column_profiles import (
    build_column_profiles,
    infer_column_candidates_from_profiles,
)
from app.features.imports.application.unknown_statements.continuations import (
    mark_continuation_previews,
)
from app.features.imports.application.unknown_statements.mapping_suggestions import (
    build_mapping_suggestions,
)
from app.features.imports.application.unknown_statements.table_detection import (
    compact_preview_rows,
    looks_like_transaction_table,
)
from app.features.imports.application.unknown_statements.table_preview_dto import (
    UnknownStatementTablePreview,
)
from app.features.imports.infrastructure.extraction.pdfplumber_extractor import ExtractedPdf


def build_table_previews(extracted: ExtractedPdf) -> list[UnknownStatementTablePreview]:
    previews: list[UnknownStatementTablePreview] = []
    for page_tables in extracted.tables_by_page:
        for table_index, table in enumerate(page_tables.tables):
            if not looks_like_transaction_table(table):
                continue
            previews.append(
                build_table_preview(
                    table,
                    page_number=page_tables.page_number,
                    table_index=table_index,
                )
            )
    return mark_continuation_previews(previews)


def build_table_preview(
    table: list[list[str | None]],
    *,
    page_number: int,
    table_index: int,
    source_type: str = "pdf_table",
) -> UnknownStatementTablePreview:
    rows = compact_preview_rows(table)
    column_profiles = build_column_profiles(table)
    column_candidates = infer_column_candidates_from_profiles(column_profiles)
    return UnknownStatementTablePreview(
        page_number=page_number,
        table_index=table_index,
        row_count=len(table),
        column_count=max((len(row) for row in table), default=0),
        preview_row_count=len(rows),
        rows=rows,
        column_candidates=column_candidates,
        column_profiles=column_profiles,
        mapping_suggestions=build_mapping_suggestions(
            column_profiles,
            column_candidates,
        ),
        source_type=source_type,
    )
