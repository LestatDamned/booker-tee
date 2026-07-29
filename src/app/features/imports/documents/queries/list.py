"""List imported documents."""

from math import ceil
from typing import Protocol
from uuid import UUID

from app.features.imports.documents.dto import (
    DEFAULT_IMPORT_DOCUMENTS_PER_PAGE,
    IMPORT_DOCUMENTS_PER_PAGE_OPTIONS,
    ImportDocumentAccountDto,
    ImportDocumentListCapabilitiesDto,
    ImportDocumentListFilterOptionsDto,
    ImportDocumentListFilters,
    ImportDocumentListItemCapabilitiesDto,
    ImportDocumentListItemDto,
    ImportDocumentListPageDto,
    ImportDocumentListPagination,
    ImportDocumentListReadModel,
    ImportDocumentListReadonlyReasonCode,
    ImportDocumentListRow,
    ImportDocumentListSummaryDto,
    ImportDocumentNextStepKind,
    ImportDocumentStatementPeriodDto,
)
from app.features.imports.domain.types import UploadedDocumentStatus
from app.features.imports.models import ParseAttemptStatus


class ImportDocumentListSource(Protocol):
    async def list_document_rows_for_workspace(
        self,
        *,
        workspace_id: UUID,
        filters: ImportDocumentListFilters,
        pagination: ImportDocumentListPagination,
    ) -> list[ImportDocumentListRow]: ...

    async def count_document_rows_for_workspace(
        self,
        *,
        workspace_id: UUID,
        filters: ImportDocumentListFilters,
    ) -> int: ...

    async def list_document_filter_accounts_for_workspace(
        self,
        workspace_id: UUID,
    ) -> list[ImportDocumentAccountDto]: ...

    async def summarize_documents_for_workspace(
        self,
        workspace_id: UUID,
    ) -> ImportDocumentListSummaryDto: ...


class ImportDocumentListReader:
    def __init__(self, source: ImportDocumentListSource) -> None:
        self._source = source

    async def read(
        self,
        *,
        workspace_id: UUID,
        workspace_name: str,
        can_upload: bool,
        filters: ImportDocumentListFilters | None = None,
        pagination: ImportDocumentListPagination | None = None,
    ) -> ImportDocumentListReadModel:
        normalized_filters = filters or ImportDocumentListFilters()
        requested_pagination = normalize_import_document_pagination(
            pagination or ImportDocumentListPagination()
        )
        total = await self._source.count_document_rows_for_workspace(
            workspace_id=workspace_id,
            filters=normalized_filters,
        )
        total_pages = max(1, ceil(total / requested_pagination.per_page))
        normalized_pagination = ImportDocumentListPagination(
            page=min(requested_pagination.page, total_pages),
            per_page=requested_pagination.per_page,
        )
        rows = await self._source.list_document_rows_for_workspace(
            workspace_id=workspace_id,
            filters=normalized_filters,
            pagination=normalized_pagination,
        )
        account_rows = await self._source.list_document_filter_accounts_for_workspace(workspace_id)
        summary = await self._source.summarize_documents_for_workspace(workspace_id)
        return ImportDocumentListReadModel(
            workspace_id=workspace_id,
            workspace_name=workspace_name,
            items=tuple(self._item(row, can_upload=can_upload) for row in rows),
            pagination=ImportDocumentListPageDto(
                page=normalized_pagination.page,
                per_page=normalized_pagination.per_page,
                total=total,
            ),
            filter_options=ImportDocumentListFilterOptionsDto(
                accounts=tuple(account_rows),
                per_page=IMPORT_DOCUMENTS_PER_PAGE_OPTIONS,
            ),
            summary=summary,
            capabilities=ImportDocumentListCapabilitiesDto(
                can_upload=can_upload,
                readonly_reason_code=(
                    None
                    if can_upload
                    else ImportDocumentListReadonlyReasonCode.IMPORT_MANAGEMENT_FORBIDDEN
                ),
            ),
        )

    @staticmethod
    def _item(
        row: ImportDocumentListRow,
        *,
        can_upload: bool,
    ) -> ImportDocumentListItemDto:
        needs_mapping = (
            row.status is UploadedDocumentStatus.REQUIRES_REVIEW
            and row.latest_parse_attempt_status is ParseAttemptStatus.REQUIRES_REVIEW
            and row.total_row_count == 0
        )
        can_map = can_upload and needs_mapping
        can_review = row.total_row_count > 0 or row.status is UploadedDocumentStatus.IMPORTED
        capabilities = ImportDocumentListItemCapabilitiesDto(
            can_open_detail=True,
            can_map=can_map,
            can_review=can_review,
        )
        if can_map:
            next_step = ImportDocumentNextStepKind.MAPPING
        elif can_review:
            next_step = ImportDocumentNextStepKind.REVIEW
        else:
            next_step = ImportDocumentNextStepKind.DETAIL
        return ImportDocumentListItemDto(
            id=row.id,
            filename=row.filename,
            status=row.status,
            created_at=row.created_at,
            file_size_bytes=row.file_size_bytes,
            detected_bank_name=row.detected_bank_name,
            statement_period=(
                ImportDocumentStatementPeriodDto(
                    start=row.statement_period_start,
                    end=row.statement_period_end,
                )
                if (row.statement_period_start is not None and row.statement_period_end is not None)
                else None
            ),
            account=(
                ImportDocumentAccountDto(
                    id=row.account_id,
                    name=row.account_name,
                    currency=row.account_currency,
                    bank_name=row.account_bank_name,
                )
                if (
                    row.account_id is not None
                    and row.account_name is not None
                    and row.account_currency is not None
                )
                else None
            ),
            total_row_count=row.total_row_count,
            reviewable_row_count=row.reviewable_row_count,
            capabilities=capabilities,
            next_step_kind=next_step,
        )


def normalize_import_document_pagination(
    pagination: ImportDocumentListPagination,
) -> ImportDocumentListPagination:
    return ImportDocumentListPagination(
        page=max(1, pagination.page),
        per_page=(
            pagination.per_page
            if pagination.per_page in IMPORT_DOCUMENTS_PER_PAGE_OPTIONS
            else DEFAULT_IMPORT_DOCUMENTS_PER_PAGE
        ),
    )
