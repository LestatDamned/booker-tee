from app.features.imports.application.unknown_statement_mappings.dto import (
    UnknownStatementMappingCommand,
)


def command_from_form_data(
    *,
    page_number: int,
    table_index: int,
    operation_date_column: int,
    description_column: int,
    amount_column: int,
    currency_column: int,
    first_data_row: int,
    default_currency: str,
    posting_date_column: int = -1,
    debit_amount_column: int = -1,
    credit_amount_column: int = -1,
    balance_after_column: int = -1,
) -> UnknownStatementMappingCommand:
    return UnknownStatementMappingCommand(
        page_number=page_number,
        table_index=table_index,
        operation_date_column=operation_date_column,
        posting_date_column=None if posting_date_column < 0 else posting_date_column,
        description_column=description_column,
        amount_column=None if amount_column < 0 else amount_column,
        currency_column=None if currency_column < 0 else currency_column,
        first_data_row=max(first_data_row, 0),
        default_currency=default_currency,
        debit_amount_column=None if debit_amount_column < 0 else debit_amount_column,
        credit_amount_column=None if credit_amount_column < 0 else credit_amount_column,
        balance_after_column=None if balance_after_column < 0 else balance_after_column,
    )
