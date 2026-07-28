from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from math import ceil
from typing import Protocol
from uuid import UUID

from app.features.imports.domain.types import UploadedDocumentStatus
from app.features.imports.models import ParseAttemptStatus

DEFAULT_IMPORT_DOCUMENTS_PER_PAGE = 25
IMPORT_DOCUMENTS_PER_PAGE_OPTIONS = (25, 50, 100)


class ImportDocumentNextStepKind(StrEnum):
    DETAIL = "detail"
    MAPPING = "mapping"
    REVIEW = "review"


class ImportDocumentListReadonlyReasonCode(StrEnum):
    IMPORT_MANAGEMENT_FORBIDDEN = "import_management_forbidden"


class ImportDocumentListState(StrEnum):
    ATTENTION = "attention"
    PROCESSING = "processing"
    COMPLETED = "completed"


class ImportDocumentListSort(StrEnum):
    CREATED_AT_DESC = "created_at_desc"
    CREATED_AT_ASC = "created_at_asc"


@dataclass(frozen=True)
class ImportDocumentListFilters:
    state: ImportDocumentListState | None = None
    account_id: UUID | None = None
    period_from: date | None = None
    period_to: date | None = None
    sort: ImportDocumentListSort = ImportDocumentListSort.CREATED_AT_DESC

    @property
    def is_active(self) -> bool:
        return any((self.state, self.account_id, self.period_from, self.period_to))


@dataclass(frozen=True)
class ImportDocumentListPagination:
    page: int = 1
    per_page: int = DEFAULT_IMPORT_DOCUMENTS_PER_PAGE

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.per_page


@dataclass(frozen=True)
class ImportDocumentListPageDto:
    page: int
    per_page: int
    total: int

    @property
    def total_pages(self) -> int:
        return max(1, ceil(self.total / self.per_page))

    @property
    def has_previous(self) -> bool:
        return self.page > 1

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages


@dataclass(frozen=True)
class ImportDocumentListRow:
    id: UUID
    filename: str
    status: UploadedDocumentStatus
    created_at: datetime
    file_size_bytes: int | None
    detected_bank_name: str | None
    statement_period_start: date | None
    statement_period_end: date | None
    account_id: UUID | None
    account_name: str | None
    account_currency: str | None
    account_bank_name: str | None
    total_row_count: int
    reviewable_row_count: int
    latest_parse_attempt_status: ParseAttemptStatus | None


@dataclass(frozen=True)
class ImportDocumentListAccountRow:
    id: UUID
    name: str
    currency: str
    bank_name: str | None


@dataclass(frozen=True)
class ImportDocumentListSummaryRow:
    total_document_count: int
    attention_document_count: int


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
    ) -> list[ImportDocumentListAccountRow]: ...

    async def summarize_documents_for_workspace(
        self,
        workspace_id: UUID,
    ) -> ImportDocumentListSummaryRow: ...


@dataclass(frozen=True)
class ImportDocumentListAccountDto:
    id: UUID
    name: str
    currency: str
    bank_name: str | None


@dataclass(frozen=True)
class ImportDocumentStatementPeriodDto:
    start: date
    end: date


@dataclass(frozen=True)
class ImportDocumentListItemCapabilitiesDto:
    can_open_detail: bool
    can_map: bool
    can_review: bool


@dataclass(frozen=True)
class ImportDocumentListItemDto:
    id: UUID
    filename: str
    status: UploadedDocumentStatus
    created_at: datetime
    file_size_bytes: int | None
    detected_bank_name: str | None
    statement_period: ImportDocumentStatementPeriodDto | None
    account: ImportDocumentListAccountDto | None
    total_row_count: int
    reviewable_row_count: int
    capabilities: ImportDocumentListItemCapabilitiesDto
    next_step_kind: ImportDocumentNextStepKind


@dataclass(frozen=True)
class ImportDocumentListCapabilitiesDto:
    can_upload: bool
    readonly_reason_code: ImportDocumentListReadonlyReasonCode | None


@dataclass(frozen=True)
class ImportDocumentListFilterOptionsDto:
    accounts: tuple[ImportDocumentListAccountDto, ...]
    per_page: tuple[int, ...]


@dataclass(frozen=True)
class ImportDocumentListSummaryDto:
    total_document_count: int
    attention_document_count: int


@dataclass(frozen=True)
class ImportDocumentListReadModel:
    workspace_id: UUID
    workspace_name: str
    items: tuple[ImportDocumentListItemDto, ...]
    pagination: ImportDocumentListPageDto
    filter_options: ImportDocumentListFilterOptionsDto
    summary: ImportDocumentListSummaryDto
    capabilities: ImportDocumentListCapabilitiesDto


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
                accounts=tuple(
                    ImportDocumentListAccountDto(
                        id=account.id,
                        name=account.name,
                        currency=account.currency,
                        bank_name=account.bank_name,
                    )
                    for account in account_rows
                ),
                per_page=IMPORT_DOCUMENTS_PER_PAGE_OPTIONS,
            ),
            summary=ImportDocumentListSummaryDto(
                total_document_count=summary.total_document_count,
                attention_document_count=summary.attention_document_count,
            ),
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
                ImportDocumentListAccountDto(
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
