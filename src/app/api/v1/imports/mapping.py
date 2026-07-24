from app.api.v1.imports.schemas import (
    ImportDocumentActionCapabilityApiResponse,
    ImportDocumentDetailAccountApiResponse,
    ImportDocumentDetailApiResponse,
    ImportDocumentDetailAttemptApiResponse,
    ImportDocumentDetailCapabilitiesApiResponse,
    ImportDocumentDetailCollectionApiResponse,
    ImportDocumentDetailRawRowApiResponse,
    ImportDocumentDetailValidationApiResponse,
    ImportDocumentDetailWorkflowApiResponse,
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
from app.features.imports.application.documents.detail_reading import (
    ImportDocumentActionCapabilityDto,
    ImportDocumentDetailReadModel,
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


class ImportDocumentDetailResponseMapper:
    @staticmethod
    def response(detail: ImportDocumentDetailReadModel) -> ImportDocumentDetailApiResponse:
        validation = detail.validation
        return ImportDocumentDetailApiResponse(
            id=detail.id,
            filename=detail.filename,
            status=detail.status,
            bank_name=detail.bank_name,
            statement_type=detail.statement_type,
            statement_period_start=detail.statement_period_start,
            statement_period_end=detail.statement_period_end,
            file_size_bytes=detail.file_size_bytes,
            created_at=detail.created_at,
            updated_at=detail.updated_at,
            account=(
                ImportDocumentDetailAccountApiResponse(
                    id=detail.account.id,
                    name=detail.account.name,
                    currency=detail.account.currency,
                )
                if detail.account is not None
                else None
            ),
            workflow=ImportDocumentDetailWorkflowApiResponse(
                upload=detail.workflow.upload,
                extract=detail.workflow.extract,
                mapping=detail.workflow.mapping,
                review=detail.workflow.review,
                ledger=detail.workflow.ledger,
            ),
            next_step=detail.next_step,
            validation=(
                ImportDocumentDetailValidationApiResponse(
                    status=validation.status,
                    reason_code=validation.reason_code,
                    message=validation.message,
                    extracted_count=validation.extracted_count,
                    calculated_total_inflow=validation.calculated_total_inflow,
                    calculated_total_outflow=validation.calculated_total_outflow,
                    ignored_row_count=validation.ignored_row_count,
                    ignored_total_inflow=validation.ignored_total_inflow,
                    ignored_total_outflow=validation.ignored_total_outflow,
                    currency=validation.currency,
                    table_count=validation.table_count,
                    needs_mapping=validation.needs_mapping,
                )
                if validation is not None
                else None
            ),
            raw_rows=ImportDocumentDetailCollectionApiResponse(
                items=[
                    ImportDocumentDetailRawRowApiResponse(
                        row_index=row.row_index,
                        status=row.status,
                        display_date=row.display_date,
                        amount=str(row.amount) if row.amount is not None else None,
                        amount_raw=row.amount_raw,
                        currency=row.currency,
                        description=row.description,
                        normalization_error=row.normalization_error,
                    )
                    for row in detail.raw_rows.items
                ],
                total=detail.raw_rows.total,
                limit=detail.raw_rows.limit,
            ),
            parse_attempts=ImportDocumentDetailCollectionApiResponse(
                items=[
                    ImportDocumentDetailAttemptApiResponse(
                        id=attempt.id,
                        status=attempt.status,
                        parser_name=attempt.parser_name,
                        parser_version=attempt.parser_version,
                        started_at=attempt.started_at,
                        finished_at=attempt.finished_at,
                        message=attempt.message,
                    )
                    for attempt in detail.parse_attempts.items
                ],
                total=detail.parse_attempts.total,
                limit=detail.parse_attempts.limit,
            ),
            capabilities=ImportDocumentDetailCapabilitiesApiResponse(
                can_manage=detail.capabilities.can_manage,
                reparse=ImportDocumentDetailResponseMapper.capability(detail.capabilities.reparse),
                ignore=ImportDocumentDetailResponseMapper.capability(detail.capabilities.ignore),
                delete=ImportDocumentDetailResponseMapper.capability(detail.capabilities.delete),
            ),
        )

    @staticmethod
    def capability(
        capability: ImportDocumentActionCapabilityDto,
    ) -> ImportDocumentActionCapabilityApiResponse:
        return ImportDocumentActionCapabilityApiResponse(
            allowed=capability.allowed,
            blocking_reason_codes=list(capability.blocking_reason_codes),
        )
