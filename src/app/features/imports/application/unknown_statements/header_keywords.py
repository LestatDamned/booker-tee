OPERATION_DATE_HEADER_KEYWORDS = (
    "дата операции",
    "дата транзакции",
    "operation date",
    "transaction date",
)
POSTING_DATE_HEADER_KEYWORDS = (
    "дата проводки",
    "дата обработки",
    "дата списания",
    "дата зачисления",
    "дата платежа",
    "posting date",
    "posted date",
    "processed date",
    "processing date",
    "booking date",
    "value date",
)
GENERIC_DATE_HEADER_KEYWORDS = (
    "дата",
    "date",
)
DATE_HEADER_KEYWORDS = (
    *OPERATION_DATE_HEADER_KEYWORDS,
    *POSTING_DATE_HEADER_KEYWORDS,
    *GENERIC_DATE_HEADER_KEYWORDS,
)
DESCRIPTION_HEADER_KEYWORDS = (
    "назначение",
    "описание",
    "description",
    "details",
    "merchant",
    "counterparty",
    "payee",
    "purpose",
)
AMOUNT_HEADER_KEYWORDS = (
    "сумма",
    "amount",
    "operation amount",
    "transaction amount",
)
DEBIT_HEADER_KEYWORDS = (
    "debit",
    "withdrawal",
    "списание",
    "списано",
    "расход",
    "расходы",
    "withdrawn",
)
CREDIT_HEADER_KEYWORDS = (
    "credit",
    "deposit",
    "зачисление",
    "зачислено",
    "приход",
    "поступление",
    "поступило",
    "received",
)
CURRENCY_HEADER_KEYWORDS = ("валюта", "currency", "ccy")
BALANCE_AFTER_HEADER_KEYWORDS = (
    "остаток",
    "balance",
    "balance after",
    "running balance",
    "available balance",
)


def header_matches_for_cell(value: str) -> list[str]:
    normalized = value.casefold()
    matches: list[str] = []
    is_posting_date = contains_any(normalized, POSTING_DATE_HEADER_KEYWORDS)
    is_operation_date = contains_any(normalized, OPERATION_DATE_HEADER_KEYWORDS)
    is_generic_date = contains_any(normalized, GENERIC_DATE_HEADER_KEYWORDS)
    if is_operation_date or (is_generic_date and not is_posting_date):
        matches.append("operation_date")
    if is_posting_date:
        matches.append("posting_date")
    if contains_any(normalized, DESCRIPTION_HEADER_KEYWORDS):
        matches.append("description")
    if contains_any(normalized, DEBIT_HEADER_KEYWORDS):
        matches.append("debit_amount")
    elif contains_any(normalized, CREDIT_HEADER_KEYWORDS):
        matches.append("credit_amount")
    elif contains_any(normalized, AMOUNT_HEADER_KEYWORDS):
        matches.append("amount")
    if contains_any(normalized, CURRENCY_HEADER_KEYWORDS):
        matches.append("currency")
    if contains_any(normalized, BALANCE_AFTER_HEADER_KEYWORDS):
        matches.append("balance_after")
    return matches


def contains_any(value: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in value for keyword in keywords)
