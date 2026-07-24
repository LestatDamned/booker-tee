from typing import Literal, cast

from app.api.v1.imports.mapping_schemas import (
    MappingAccountApiResponse,
    MappingCapabilityApiResponse,
    MappingColumnCandidateApiResponse,
    MappingCommandApiModel,
    MappingPreviewApiResponse,
    MappingPreviewRowApiResponse,
    MappingReadApiResponse,
    MappingSourceRowApiResponse,
    MappingSourceTableApiResponse,
    MappingSuggestionApiResponse,
    MappingSuggestionReasonApiResponse,
    MappingTableRefApiModel,
    MappingTemplateApiResponse,
    MappingWarningApiResponse,
)
from app.features.imports.application.unknown_statement_mappings.dto import (
    UnknownStatementMappingCommand,
)
from app.features.imports.application.unknown_statement_mappings.read_models import (
    MappingSourceTableDto,
    MappingSuggestionDto,
    MappingTableRefDto,
    UnknownStatementMappingPreviewResult,
    UnknownStatementMappingReadModel,
)


class UnknownStatementMappingResponseMapper:
    @staticmethod
    def read(mapping: UnknownStatementMappingReadModel) -> MappingReadApiResponse:
        return MappingReadApiResponse(
            document_id=mapping.document_id,
            filename=mapping.filename,
            status=mapping.status,
            bank_name=mapping.bank_name,
            statement_type=mapping.statement_type,
            account=(
                MappingAccountApiResponse(
                    id=mapping.account.id,
                    name=mapping.account.name,
                    currency=mapping.account.currency,
                )
                if mapping.account is not None
                else None
            ),
            default_currency=mapping.default_currency,
            capability=MappingCapabilityApiResponse(
                allowed=mapping.capability.allowed,
                blocking_reason_codes=list(mapping.capability.blocking_reason_codes),
            ),
            default_mapping=UnknownStatementMappingResponseMapper.command(mapping.default_mapping),
            default_source=mapping.default_source,
            selected_template_id=mapping.selected_template_id,
            templates=[
                MappingTemplateApiResponse(id=template.id, name=template.name)
                for template in mapping.templates
            ],
            tables=[
                UnknownStatementMappingResponseMapper.source_table(table)
                for table in mapping.tables
            ],
            total_table_count=mapping.total_table_count,
            tables_truncated=mapping.tables_truncated,
        )

    @staticmethod
    def preview(
        preview: UnknownStatementMappingPreviewResult,
    ) -> MappingPreviewApiResponse:
        return MappingPreviewApiResponse(
            rows=[
                MappingPreviewRowApiResponse(
                    table_ref=UnknownStatementMappingResponseMapper.table_ref(row.table_ref),
                    source_row_number=row.source_row_number,
                    operation_date=row.operation_date,
                    operation_date_raw=row.operation_date_raw,
                    posting_date=row.posting_date,
                    posting_date_raw=row.posting_date_raw,
                    description=row.description,
                    amount=row.amount,
                    amount_raw=row.amount_raw,
                    currency=row.currency,
                    balance_after=row.balance_after,
                    balance_after_raw=row.balance_after_raw,
                    status=cast(Literal["valid", "error"], row.status),
                    error_codes=list(row.error_codes),
                )
                for row in preview.rows
            ],
            total_row_count=preview.total_row_count,
            valid_row_count=preview.valid_row_count,
            invalid_row_count=preview.invalid_row_count,
            row_limit=preview.row_limit,
            rows_truncated=preview.rows_truncated,
            compatible_tables=[
                UnknownStatementMappingResponseMapper.table_ref(table)
                for table in preview.compatible_tables
            ],
            warnings=[
                MappingWarningApiResponse(
                    code=warning.code,
                    severity=cast(
                        Literal["warning", "error"],
                        warning.severity,
                    ),
                    fields=[_warning_field(field) for field in warning.fields],
                    affected_row_count=warning.affected_row_count,
                )
                for warning in preview.warnings
            ],
            can_import=preview.can_import,
        )

    @staticmethod
    def source_table(table: MappingSourceTableDto) -> MappingSourceTableApiResponse:
        return MappingSourceTableApiResponse(
            ref=UnknownStatementMappingResponseMapper.table_ref(table.ref),
            source_type=table.source_type,
            row_count=table.row_count,
            column_count=table.column_count,
            is_continuation=table.is_continuation,
            sample_rows=[
                MappingSourceRowApiResponse(
                    row_number=row.row_number,
                    cells=list(row.cells),
                )
                for row in table.sample_rows
            ],
            candidates=[
                MappingColumnCandidateApiResponse(
                    field=candidate.field,
                    column_index=candidate.column_index,
                    header=candidate.header,
                    confidence=candidate.confidence,
                )
                for candidate in table.candidates
            ],
            suggestion=(
                UnknownStatementMappingResponseMapper.suggestion(table.suggestion)
                if table.suggestion is not None
                else None
            ),
        )

    @staticmethod
    def suggestion(
        suggestion: MappingSuggestionDto,
    ) -> MappingSuggestionApiResponse:
        return MappingSuggestionApiResponse(
            mapping=UnknownStatementMappingResponseMapper.command(suggestion.command),
            confidence=suggestion.confidence,
            reasons=[
                MappingSuggestionReasonApiResponse(
                    field=reason.field,
                    column_index=reason.column_index,
                    header=reason.header,
                    evidence=reason.evidence,
                    matched_count=reason.matched_count,
                    sample_count=reason.sample_count,
                )
                for reason in suggestion.reasons
            ],
            warning_codes=list(suggestion.warning_codes),
        )

    @staticmethod
    def command(command: UnknownStatementMappingCommand) -> MappingCommandApiModel:
        return MappingCommandApiModel(
            table_ref=MappingTableRefApiModel(
                page_number=command.page_number,
                table_index=command.table_index,
            ),
            operation_date_column=command.operation_date_column,
            posting_date_column=command.posting_date_column,
            description_column=command.description_column,
            amount_column=command.amount_column,
            debit_amount_column=command.debit_amount_column,
            credit_amount_column=command.credit_amount_column,
            currency_column=command.currency_column,
            balance_after_column=command.balance_after_column,
            first_data_row_number=command.first_data_row + 1,
            default_currency=command.default_currency,
            unsigned_amount_direction=command.unsigned_amount_direction,
        )

    @staticmethod
    def table_ref(table: MappingTableRefDto) -> MappingTableRefApiModel:
        return MappingTableRefApiModel(
            page_number=table.page_number,
            table_index=table.table_index,
        )


def _warning_field(field: str) -> str:
    return {
        "operation_date": "operationDateColumn",
        "posting_date": "postingDateColumn",
        "description": "descriptionColumn",
        "amount": "amountColumn",
        "debit_amount": "debitAmountColumn",
        "credit_amount": "creditAmountColumn",
        "currency": "currencyColumn",
        "balance_after": "balanceAfterColumn",
        "unsigned_amount_direction": "unsignedAmountDirection",
    }.get(field, field)
