from app.api.v1.imports.schemas import (
    ImportDocumentListAccountApiResponse,
    ImportDocumentListApiResponse,
    ImportDocumentListCapabilitiesApiResponse,
    ImportDocumentListFilterOptionsApiResponse,
    ImportDocumentListItemApiResponse,
    ImportDocumentListItemCapabilitiesApiResponse,
    ImportDocumentListPaginationApiResponse,
    ImportDocumentListSummaryApiResponse,
    ImportDocumentStatementPeriodApiResponse,
)
from app.features.imports.application.documents.listing import ImportDocumentListReadModel


class ImportDocumentListResponseMapper:
    @staticmethod
    def response(documents: ImportDocumentListReadModel) -> ImportDocumentListApiResponse:
        return ImportDocumentListApiResponse(
            workspace_id=documents.workspace_id,
            workspace_name=documents.workspace_name,
            items=[
                ImportDocumentListItemApiResponse(
                    id=item.id,
                    filename=item.filename,
                    status=item.status,
                    created_at=item.created_at,
                    file_size_bytes=item.file_size_bytes,
                    account=(
                        ImportDocumentListAccountApiResponse(
                            id=item.account.id,
                            name=item.account.name,
                            currency=item.account.currency,
                            bank_name=item.account.bank_name,
                        )
                        if item.account is not None
                        else None
                    ),
                    detected_bank_name=item.detected_bank_name,
                    statement_period=(
                        ImportDocumentStatementPeriodApiResponse(
                            start=item.statement_period.start,
                            end=item.statement_period.end,
                        )
                        if item.statement_period is not None
                        else None
                    ),
                    total_row_count=item.total_row_count,
                    reviewable_row_count=item.reviewable_row_count,
                    capabilities=ImportDocumentListItemCapabilitiesApiResponse(
                        can_open_detail=item.capabilities.can_open_detail,
                        can_map=item.capabilities.can_map,
                        can_review=item.capabilities.can_review,
                    ),
                    next_step_kind=item.next_step_kind,
                )
                for item in documents.items
            ],
            pagination=ImportDocumentListPaginationApiResponse(
                page=documents.pagination.page,
                per_page=documents.pagination.per_page,
                total=documents.pagination.total,
                total_pages=documents.pagination.total_pages,
                has_previous=documents.pagination.has_previous,
                has_next=documents.pagination.has_next,
            ),
            filter_options=ImportDocumentListFilterOptionsApiResponse(
                accounts=[
                    ImportDocumentListAccountApiResponse(
                        id=account.id,
                        name=account.name,
                        currency=account.currency,
                        bank_name=account.bank_name,
                    )
                    for account in documents.filter_options.accounts
                ],
                per_page=list(documents.filter_options.per_page),
            ),
            summary=ImportDocumentListSummaryApiResponse(
                total_document_count=documents.summary.total_document_count,
                attention_document_count=documents.summary.attention_document_count,
            ),
            capabilities=ImportDocumentListCapabilitiesApiResponse(
                can_upload=documents.capabilities.can_upload,
                readonly_reason_code=documents.capabilities.readonly_reason_code,
            ),
        )
