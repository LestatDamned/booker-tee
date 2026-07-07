from collections.abc import Sequence
from decimal import Decimal
from typing import cast

from app.features.accounts.models import AccountType
from app.features.imports.models import (
    ParseAttemptStatus,
    RawTransactionStatus,
    UploadedDocumentStatus,
)


def document_status_label(status: UploadedDocumentStatus) -> str:
    labels = {
        UploadedDocumentStatus.UPLOADED: "загружен",
        UploadedDocumentStatus.PENDING_PARSE: "ожидает парсинга",
        UploadedDocumentStatus.PARSING: "парсится",
        UploadedDocumentStatus.PARSED: "распознан",
        UploadedDocumentStatus.REQUIRES_REVIEW: "нужна проверка",
        UploadedDocumentStatus.FAILED_TO_PARSE: "ошибка парсинга",
        UploadedDocumentStatus.IMPORTED: "импортирован",
        UploadedDocumentStatus.IGNORED: "игнорируется",
    }
    return labels.get(status, status.value)


def validation_status_label(status: str) -> str:
    labels = {
        "valid": "сошлось",
        "mismatch": "не совпадает",
        "unavailable": "нет итогов",
        "needs_review": "нужна проверка",
        "needs_mapping": "нужна настройка",
        "failed": "ошибка",
        "failed_to_parse": "ошибка парсинга",
    }
    return labels.get(status, status)


def parse_attempt_status_label(status: ParseAttemptStatus) -> str:
    labels = {
        ParseAttemptStatus.RUNNING: "в процессе",
        ParseAttemptStatus.SUCCESS: "успешно",
        ParseAttemptStatus.REQUIRES_REVIEW: "нужна проверка",
        ParseAttemptStatus.FAILED: "ошибка",
    }
    return labels.get(status, status.value)


def raw_transaction_status_label(status: RawTransactionStatus) -> str:
    labels = {
        RawTransactionStatus.EXTRACTED: "извлечено",
        RawTransactionStatus.NORMALIZED: "нормализовано",
        RawTransactionStatus.SUGGESTED: "предложено",
        RawTransactionStatus.NEEDS_REVIEW: "нужна проверка",
        RawTransactionStatus.MATCHED: "связано",
        RawTransactionStatus.IGNORED: "игнор",
        RawTransactionStatus.DUPLICATE: "дубликат",
        RawTransactionStatus.POSSIBLE_DUPLICATE: "возможный дубль",
        RawTransactionStatus.FAILED: "ошибка",
        RawTransactionStatus.CONFIRMED: "подтверждено",
    }
    return labels.get(status, status.value)


def account_type_label(account_type: AccountType) -> str:
    labels = {
        AccountType.CASH: "наличные",
        AccountType.CARD: "карта",
        AccountType.DEPOSIT: "депозит",
        AccountType.CHECKING: "расчетный счет",
        AccountType.OTHER: "другое",
    }
    return labels.get(account_type, account_type.value)


def statement_type_label(value: object) -> str:
    labels = {
        "card_statement": "карточная выписка",
        "account_statement": "выписка по счету",
        "deposit_statement": "выписка по вкладу",
    }
    status = string_value(value)
    return labels.get(status, status)


def document_message_label(value: object) -> str:
    message = string_value(value)
    labels = {
        (
            "Parser is not available for this statement yet, but transaction-like tables "
            "were extracted. Configure column mapping to import it."
        ): (
            "Для этой выписки пока нет готового парсера, но найдены таблицы, похожие "
            "на операции. Настройте колонки, чтобы импортировать строки."
        ),
        (
            "Parser is not available for this statement yet. No transaction table was "
            "detected, but transaction-like text lines were converted into a reviewable "
            "table. Check the mapping before importing."
        ): (
            "Для этой выписки пока нет готового парсера. Таблица операций не найдена, "
            "но похожие на операции строки текста собраны в таблицу для проверки."
        ),
        (
            "Parser is not available for this statement yet. Text was extracted, but no "
            "transaction table or transaction-like text lines were detected."
        ): (
            "Для этой выписки пока нет готового парсера. Текст извлечен, но таблица "
            "операций или похожие на операции строки не найдены."
        ),
        (
            "Parser is not available for this statement yet, and no readable text was "
            "extracted. OCR may be required before import."
        ): (
            "Для этой выписки пока нет готового парсера, и читаемый текст не извлечен. "
            "Перед импортом может понадобиться OCR."
        ),
    }
    return labels.get(message, message)


def parser_label(parser_name: str, parser_version: str | None) -> str:
    if not parser_version:
        return parser_name
    return f"{parser_name} {parser_version}"


def table_source_label(source_type: object, table_index: int) -> str:
    if source_type == "text_candidate":
        return "из текста"
    return f"таблица {table_index + 1}"


def table_row_count_label(*, row_count: int, preview_row_count: int | None) -> str:
    if preview_row_count is not None and preview_row_count < row_count:
        return f"показано {preview_row_count} из {row_count} строк"
    return f"{row_count} строк"


def table_rows(value: object) -> Sequence[Sequence[object]]:
    if not isinstance(value, list):
        return []
    return cast(Sequence[Sequence[object]], value)


def int_value(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdecimal():
        return int(value)
    return 0


def optional_int_value(value: object) -> int | None:
    if value is None:
        return None
    return int_value(value)


def money_value(value: object, currency: object) -> str:
    if value in {None, ""}:
        return ""
    currency_label = string_value(currency)
    if not currency_label:
        return str(value)
    return f"{value} {currency_label}"


def money_tone(value: Decimal | None) -> str | None:
    if value is None:
        return None
    if value > 0:
        return "income"
    if value < 0:
        return "expense"
    return None


def string_value(value: object, *, fallback: str = "") -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return fallback
    return str(value)
