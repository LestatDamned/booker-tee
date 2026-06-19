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
    best_header_row_index,
    compact_preview_rows,
    looks_like_transaction_table,
)
from app.features.imports.application.unknown_statements.table_preview_dto import (
    UnknownStatementTablePreview,
)
from app.features.imports.infrastructure.extraction.extracted_statement import ExtractedStatement


def build_table_previews(extracted: ExtractedStatement) -> list[UnknownStatementTablePreview]:
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
    header_row_index = best_header_row_index([[cell or "" for cell in row] for row in table])
    profiled_table = table[header_row_index:] if header_row_index > 0 else table
    column_profiles = build_column_profiles(profiled_table)
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
            row_offset=header_row_index,
        ),
        source_type=source_type,
    )
