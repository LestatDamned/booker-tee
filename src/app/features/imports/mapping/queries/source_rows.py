from typing import Protocol
from uuid import UUID

from app.features.imports.documents.dto import ImportDocumentSnapshot
from app.features.imports.mapping.dto import (
    MappingSourceRowDto,
    MappingSourceRowsDto,
    MappingTableRefDto,
)
from app.features.imports.mapping.queries.overview import latest_mapping_raw_tables
from app.features.imports.mapping.raw_tables import find_raw_table

MAX_MAPPING_SOURCE_SAMPLE_COLUMNS = 32
MAX_MAPPING_SOURCE_CELL_CHARS = 500
MAX_MAPPING_SOURCE_WINDOW_ROWS = 50


class MappingSourceRowsDocumentReader(Protocol):
    async def get_document_snapshot(
        self,
        workspace_id: UUID,
        document_id: UUID,
    ) -> ImportDocumentSnapshot | None: ...


class StatementMappingSourceRowsReader:
    def __init__(self, documents: MappingSourceRowsDocumentReader) -> None:
        self._documents = documents

    async def read(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
        page_number: int,
        table_index: int,
        start_row_number: int,
        row_limit: int,
    ) -> MappingSourceRowsDto | None:
        snapshot = await self._documents.get_document_snapshot(workspace_id, document_id)
        if snapshot is None:
            return None
        raw_table = find_raw_table(
            latest_mapping_raw_tables(snapshot),
            page_number=page_number,
            table_index=table_index,
        )
        if not raw_table:
            return None
        bounded_limit = min(max(row_limit, 1), MAX_MAPPING_SOURCE_WINDOW_ROWS)
        start_index = min(max(start_row_number - 1, 0), len(raw_table) - 1)
        selected_rows = raw_table[start_index : start_index + bounded_limit]
        rows = tuple(
            MappingSourceRowDto(
                row_number=start_index + index + 1,
                cells=tuple(
                    cell[:MAX_MAPPING_SOURCE_CELL_CHARS]
                    for cell in row[:MAX_MAPPING_SOURCE_SAMPLE_COLUMNS]
                ),
            )
            for index, row in enumerate(selected_rows)
        )
        return MappingSourceRowsDto(
            table_ref=MappingTableRefDto(page_number, table_index),
            rows=rows,
            total_row_count=len(raw_table),
            start_row_number=start_index + 1,
            row_limit=bounded_limit,
            has_previous=start_index > 0,
            has_next=start_index + len(rows) < len(raw_table),
        )
