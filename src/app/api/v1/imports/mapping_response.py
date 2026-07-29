from typing import Literal, cast

from app.api.v1.imports.mapping_schemas import (
    MappingAccountApiResponse,
    MappingBalanceReconciliationApiResponse,
    MappingCapabilityApiResponse,
    MappingColumnCandidateApiResponse,
    MappingCommandApiModel,
    MappingControlTotalCandidateApiResponse,
    MappingControlTotalCellApiModel,
    MappingPreviewApiResponse,
    MappingPreviewRowApiResponse,
    MappingReadApiResponse,
    MappingResolvedControlTotalApiResponse,
    MappingSourceRowApiResponse,
    MappingSourceRowsApiResponse,
    MappingSourceTableApiResponse,
    MappingSuggestionApiResponse,
    MappingSuggestionReasonApiResponse,
    MappingTableRefApiModel,
    MappingTemplateApiResponse,
    MappingWarningApiResponse,
)
from app.features.imports.application.unknown_statement_mappings.read_models import (
    MappingSourceRowsDto,
    MappingSourceTableDto,
    MappingSuggestionDto,
    MappingTableRefDto,
    UnknownStatementMappingPreviewResult,
    UnknownStatementMappingReadModel,
)
from app.features.imports.mapping.dto import (
    MappingControlTotalCellRef,
    StatementMappingSpec,
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
                MappingAccountApiResponse.model_validate(
                    mapping.account,
                    from_attributes=True,
                )
                if mapping.account is not None
                else None
            ),
            default_currency=mapping.default_currency,
            capability=MappingCapabilityApiResponse.model_validate(
                mapping.capability,
                from_attributes=True,
            ),
            default_mapping=UnknownStatementMappingResponseMapper.spec(mapping.default_mapping),
            default_source=mapping.default_source,
            selected_template_id=mapping.selected_template_id,
            templates=[
                MappingTemplateApiResponse.model_validate(template, from_attributes=True)
                for template in mapping.templates
            ],
            tables=[
                UnknownStatementMappingResponseMapper.source_table(table)
                for table in mapping.tables
            ],
            control_total_candidates=[
                MappingControlTotalCandidateApiResponse(
                    kind=cast(
                        Literal["opening_balance", "closing_balance"],
                        candidate.kind,
                    ),
                    cell=UnknownStatementMappingResponseMapper.control_total_cell(candidate.cell),
                    label=candidate.label,
                    raw_value=candidate.raw_value,
                    amount=candidate.amount,
                    currency=candidate.currency,
                    confidence=candidate.confidence,
                )
                for candidate in mapping.control_total_candidates
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
            control_totals=[
                MappingResolvedControlTotalApiResponse(
                    kind=cast(
                        Literal["opening_balance", "closing_balance"],
                        total.kind,
                    ),
                    cell=UnknownStatementMappingResponseMapper.control_total_cell(total.cell),
                    raw_value=total.raw_value,
                    amount=total.amount,
                    currency=total.currency,
                )
                for total in preview.control_totals
            ],
            reconciliation=(
                MappingBalanceReconciliationApiResponse.model_validate(
                    preview.reconciliation,
                    from_attributes=True,
                )
                if preview.reconciliation is not None
                else None
            ),
            can_import=preview.can_import,
        )

    @staticmethod
    def source_rows(rows: MappingSourceRowsDto) -> MappingSourceRowsApiResponse:
        return MappingSourceRowsApiResponse(
            table_ref=UnknownStatementMappingResponseMapper.table_ref(rows.table_ref),
            rows=[
                MappingSourceRowApiResponse.model_validate(row, from_attributes=True)
                for row in rows.rows
            ],
            total_row_count=rows.total_row_count,
            start_row_number=rows.start_row_number,
            row_limit=rows.row_limit,
            has_previous=rows.has_previous,
            has_next=rows.has_next,
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
                MappingSourceRowApiResponse.model_validate(row, from_attributes=True)
                for row in table.sample_rows
            ],
            candidates=[
                MappingColumnCandidateApiResponse.model_validate(
                    candidate,
                    from_attributes=True,
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
            mapping=UnknownStatementMappingResponseMapper.spec(suggestion.spec),
            reasons=[
                MappingSuggestionReasonApiResponse.model_validate(
                    reason,
                    from_attributes=True,
                )
                for reason in suggestion.reasons
            ],
            warning_codes=list(suggestion.warning_codes),
        )

    @staticmethod
    def spec(spec: StatementMappingSpec) -> MappingCommandApiModel:
        return MappingCommandApiModel(
            table_ref=MappingTableRefApiModel(
                page_number=spec.page_number,
                table_index=spec.table_index,
            ),
            operation_date_column=spec.operation_date_column,
            posting_date_column=spec.posting_date_column,
            description_column=spec.description_column,
            amount_column=spec.amount_column,
            debit_amount_column=spec.debit_amount_column,
            credit_amount_column=spec.credit_amount_column,
            currency_column=spec.currency_column,
            balance_after_column=spec.balance_after_column,
            first_data_row_number=spec.first_data_row + 1,
            default_currency=spec.default_currency,
            unsigned_amount_direction=spec.unsigned_amount_direction,
            opening_balance_cell=(
                UnknownStatementMappingResponseMapper.control_total_cell(spec.opening_balance_cell)
                if spec.opening_balance_cell is not None
                else None
            ),
            closing_balance_cell=(
                UnknownStatementMappingResponseMapper.control_total_cell(spec.closing_balance_cell)
                if spec.closing_balance_cell is not None
                else None
            ),
        )

    @staticmethod
    def table_ref(table: MappingTableRefDto) -> MappingTableRefApiModel:
        return MappingTableRefApiModel.model_validate(table, from_attributes=True)

    @staticmethod
    def control_total_cell(
        cell: MappingControlTotalCellRef,
    ) -> MappingControlTotalCellApiModel:
        return MappingControlTotalCellApiModel(
            table_ref=MappingTableRefApiModel(
                page_number=cell.page_number,
                table_index=cell.table_index,
            ),
            row_number=cell.row_number + 1,
            column_index=cell.column_index,
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
