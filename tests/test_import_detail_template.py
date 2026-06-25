from datetime import date, datetime
from decimal import Decimal
from typing import Any, cast
from uuid import uuid4

from app.features.accounts.models import AccountType
from app.features.imports.application.unknown_statement_mappings.dto import (
    UnknownStatementMappedRow,
    UnknownStatementMappingCommand,
    UnknownStatementMappingPreview,
    UnknownStatementMappingWarning,
)
from app.features.imports.mapping.dto import (
    ImportAccountRef,
    ImportDocumentDetailView,
    ImportParseAttemptView,
    ImportRawTransactionRow,
)
from app.features.imports.models import (
    ParseAttemptStatus,
    RawTransactionStatus,
    UploadedDocumentStatus,
)
from app.templating import create_templates


def test_import_detail_template_shows_readable_account_reference() -> None:
    account_id = uuid4()
    view = ImportDocumentDetailView(
        id=uuid4(),
        original_filename="statement.pdf",
        status=UploadedDocumentStatus.PARSED,
        sha256_hash="a" * 64,
        storage_key="workspace/document/statement.pdf",
        bank_name=None,
        statement_type=None,
        account=ImportAccountRef(
            id=account_id,
            name="ВТБ вклад",
            type=AccountType.DEPOSIT,
            currency="RUB",
        ),
        validation=None,
        parse_attempts=[],
        raw_transactions=[],
    )
    templates = create_templates()
    cast(Any, templates.env.globals)["url_for"] = lambda _name, **values: values.get("path", "")

    html = templates.env.get_template("imports/detail.html").render(
        app_name="Booker Tee",
        view=view,
    )

    assert "ВТБ вклад" in html
    assert "депозит" in html
    assert "RUB" in html
    assert "Отладочные данные документа" in html
    assert f"ID счета {account_id}" in html


def test_import_detail_template_keeps_failed_parse_page_compact() -> None:
    document_id = uuid4()
    attempt_id = uuid4()
    view = ImportDocumentDetailView(
        id=document_id,
        original_filename="broken.pdf",
        status=UploadedDocumentStatus.FAILED_TO_PARSE,
        sha256_hash="831fb532af945a1753654723284f16983acd3e245d6b82d77e5ac9cd1c65efa3",
        storage_key=f"workspace/{document_id}/broken.pdf",
        bank_name=None,
        statement_type=None,
        account=None,
        raw_transactions=[],
        parse_attempts=[
            ImportParseAttemptView(
                id=attempt_id,
                status=ParseAttemptStatus.FAILED,
                parser_name="expobank_card_statement_v1",
                parser_version="0.1",
                started_at=datetime(2026, 6, 13, 11, 5, 8),
                finished_at=datetime(2026, 6, 13, 11, 5, 8),
                error_message="PdfminerException: No /Root object!",
                validation_report=None,
                raw_tables=None,
                raw_text_by_page=None,
            ),
        ],
        validation=None,
    )
    templates = create_templates()
    cast(Any, templates.env.globals)["url_for"] = lambda _name, **values: values.get("path", "")

    html = templates.env.get_template("imports/detail.html").render(
        app_name="Booker Tee",
        view=view,
    )

    assert "document-detail-grid" in html
    assert "empty-state" in html
    assert "parse-attempt-list" in html
    assert "parse-attempt-card" in html
    assert "Отладочные данные документа" in html
    assert "Технические детали" not in html
    assert f"ID {document_id}" in html
    assert f"ID {attempt_id}" in html
    assert "PdfminerException: No /Root object!" in html
    assert f'<td class="status">{attempt_id}</td>' not in html


def test_import_detail_raw_transactions_are_money_first_and_use_ru_date() -> None:
    parse_attempt_id = uuid4()
    view = ImportDocumentDetailView(
        id=uuid4(),
        original_filename="statement.pdf",
        status=UploadedDocumentStatus.REQUIRES_REVIEW,
        sha256_hash="a" * 64,
        storage_key="workspace/document/statement.pdf",
        bank_name=None,
        statement_type=None,
        account=None,
        validation=None,
        parse_attempts=[],
        raw_transactions=[
            ImportRawTransactionRow(
                row_index=0,
                status=RawTransactionStatus.NORMALIZED,
                parse_attempt_id=parse_attempt_id,
                display_date=date(2026, 5, 26),
                amount=Decimal("-2509.00"),
                amount_raw="-2509.00",
                currency="RUB",
                description="Оплата товаров и услуг. SBER*5411*SAMOKAT.",
                normalization_error="",
            ),
        ],
    )
    templates = create_templates()
    cast(Any, templates.env.globals)["url_for"] = lambda _name, **values: values.get("path", "")

    html = templates.env.get_template("imports/detail.html").render(
        app_name="Booker Tee",
        view=view,
    )

    assert "raw-transaction-head" in html
    assert "26.05.2026" in html
    assert "2026-05-26" not in html
    assert "Технические детали</summary>" not in html
    assert "ID строки" in html
    assert html.index("-2509.00") < html.index("26.05.2026")
    assert html.index("-2509.00") < html.index("нормализовано")


def test_import_detail_template_shows_unknown_statement_mapping_preview() -> None:
    document_id = uuid4()
    attempt_id = uuid4()
    validation: dict[str, object] = {
        "status": "needs_mapping",
        "message": "Configure column mapping to import it.",
        "detected_bank_name": "Ozon Bank",
        "detected_statement_type": "card_statement",
        "text_based": True,
        "page_count": 14,
        "table_count": 3,
        "table_previews": [
            {
                "page_number": 1,
                "table_index": 0,
                "row_count": 2,
                "column_count": 5,
                "rows": [
                    ["Дата операции", "Документ", "Назначение платежа", "Сумма операции"],
                    ["12.05.2026 15:42:10", "1", "Оплата товаров по карте", "-842,00 ₽"],
                ],
                "column_candidates": [
                    {
                        "field": "operation_date",
                        "column_index": 0,
                        "header": "Дата операции",
                        "confidence": 0.95,
                    },
                    {
                        "field": "amount",
                        "column_index": 3,
                        "header": "Сумма операции",
                        "confidence": 0.85,
                    },
                ],
                "mapping_suggestions": [
                    {
                        "operation_date_column": 0,
                        "description_column": 2,
                        "amount_column": 3,
                        "debit_amount_column": None,
                        "credit_amount_column": None,
                        "currency_column": 4,
                        "first_data_row": 1,
                        "confidence": 0.91,
                        "reasons": [
                            {
                                "field": "operation_date",
                                "column_index": 0,
                                "header": "Дата операции",
                                "evidence": "header_match",
                                "matched_count": None,
                                "sample_count": None,
                            },
                            {
                                "field": "amount",
                                "column_index": 3,
                                "header": "Сумма операции",
                                "evidence": "header_match",
                                "matched_count": None,
                                "sample_count": None,
                            },
                        ],
                        "warnings": [],
                    }
                ],
            },
            {
                "page_number": 2,
                "table_index": 0,
                "row_count": 8,
                "column_count": 5,
                "preview_row_count": 5,
                "rows": [
                    ["30.05.2026", "10853995013", "Оплата товаров", "-390,00 ₽", "-390,00 ₽"],
                    ["30.05.2026", "1084543089", "Кафе", "-385,87 ₽", "-385,87 ₽"],
                    ["29.05.2026", "1083359460", "Такси", "-538,87 ₽", "-538,87 ₽"],
                    ["29.05.2026", "1083350899", "Сервис", "-286,00 ₽", "-286,00 ₽"],
                    ["29.05.2026", "1082954888", "Маркет", "-809,92 ₽", "-809,92 ₽"],
                ],
                "column_candidates": [
                    {
                        "field": "operation_date",
                        "column_index": 2,
                        "header": "Оплата товаров по карте 3977 сумма 390.00",
                        "confidence": 0.75,
                    }
                ],
                "mapping_suggestions": [],
                "is_continuation": True,
                "continued_from_page_number": 1,
                "continued_from_table_index": 0,
                "continuation_mapping_fields": [
                    {"field": "operation_date", "column_index": 0},
                    {"field": "description", "column_index": 2},
                    {"field": "amount", "column_index": 3},
                ],
            },
        ],
    }
    view = ImportDocumentDetailView(
        id=document_id,
        original_filename="ozonbank_card_statement.pdf",
        status=UploadedDocumentStatus.REQUIRES_REVIEW,
        sha256_hash="a" * 64,
        storage_key=f"workspace/{document_id}/ozonbank_card_statement.pdf",
        bank_name="Ozon Bank",
        statement_type="card_statement",
        account=None,
        raw_transactions=[],
        parse_attempts=[
            ImportParseAttemptView(
                id=attempt_id,
                status=ParseAttemptStatus.REQUIRES_REVIEW,
                parser_name="pdfplumber_raw_extractor",
                parser_version="0.1",
                started_at=datetime(2026, 6, 13, 11, 5, 8),
                finished_at=datetime(2026, 6, 13, 11, 5, 8),
                error_message=None,
                validation_report=validation,
                raw_tables=None,
                raw_text_by_page=None,
            ),
        ],
        validation=validation,
    )
    templates = create_templates()
    cast(Any, templates.env.globals)["url_for"] = lambda _name, **values: values.get("path", "")

    html = templates.env.get_template("imports/detail.html").render(
        app_name="Booker Tee",
        view=view,
    )

    assert "Нужна настройка импорта" in html
    assert "Ozon Bank" in html
    assert "карточная выписка" in html
    assert "текстовый" in html
    assert "Предпросмотр таблиц" in html
    assert "preview-meta" in html
    assert "Предложение маппинга · 91%" in html
    assert "дата: колонка 1 выбрана по заголовку" in html
    assert "operation_date: колонка 1" in html
    assert "amount: колонка 4" in html
    assert "показано 5 из 8 строк" in html
    assert "Продолжение таблицы · страница 1 · таблица 1" in html
    assert "дата: колонка 1" in html
    assert "operation_date: колонка 3 · Оплата товаров" not in html
    assert "Оплата товаров по карте" in html


def test_unknown_statement_mapping_template_shows_form_and_preview() -> None:
    document_id = uuid4()
    view = ImportDocumentDetailView(
        id=document_id,
        original_filename="ozonbank_card_statement.pdf",
        status=UploadedDocumentStatus.REQUIRES_REVIEW,
        sha256_hash="a" * 64,
        storage_key=f"workspace/{document_id}/ozonbank_card_statement.pdf",
        bank_name="Ozon Bank",
        statement_type="card_statement",
        account=None,
        raw_transactions=[],
        parse_attempts=[],
        validation=None,
    )
    table = {
        "page_number": 1,
        "table_index": 0,
        "row_count": 2,
        "column_count": 5,
        "rows": [
            ["Дата операции", "Документ", "Назначение платежа", "Сумма операции", "Валюта"],
            ["12.05.2026 15:42:10", "1", "Оплата товаров по карте", "-842,00 ₽", "RUB"],
        ],
        "column_candidates": [
            {
                "field": "operation_date",
                "column_index": 0,
                "header": "Дата операции",
                "confidence": 0.95,
            }
        ],
        "mapping_suggestions": [
            {
                "operation_date_column": 0,
                "description_column": 2,
                "amount_column": 3,
                "debit_amount_column": None,
                "credit_amount_column": None,
                "currency_column": 4,
                "first_data_row": 1,
                "confidence": 0.91,
                "reasons": [
                    {
                        "field": "operation_date",
                        "column_index": 0,
                        "header": "Дата операции",
                        "evidence": "header_match",
                        "matched_count": None,
                        "sample_count": None,
                    },
                    {
                        "field": "amount",
                        "column_index": 3,
                        "header": "Сумма операции",
                        "evidence": "header_match",
                        "matched_count": None,
                        "sample_count": None,
                    },
                ],
                "warnings": [
                    {
                        "code": "partial_debit_credit_columns",
                        "fields": ["debit_amount"],
                    }
                ],
            }
        ],
    }
    command = UnknownStatementMappingCommand(
        page_number=1,
        table_index=0,
        operation_date_column=0,
        description_column=2,
        amount_column=3,
        currency_column=4,
        first_data_row=1,
        default_currency="RUB",
    )
    preview = UnknownStatementMappingPreview(
        rows=[
            UnknownStatementMappedRow(
                page_number=1,
                table_index=0,
                source_row_number=1,
                operation_date_raw="12.05.2026 15:42:10",
                operation_date=date(2026, 5, 12),
                description_raw="Оплата товаров по карте",
                description="Оплата товаров по карте",
                amount_raw="-842,00 ₽",
                amount=Decimal("-842.00"),
                currency_raw="RUB",
                currency="RUB",
                status="valid",
                error="",
            )
        ],
        warnings=[
            UnknownStatementMappingWarning(
                code="high_error_rate",
                severity="warning",
            )
        ],
    )
    templates = create_templates()
    cast(Any, templates.env.globals)["url_for"] = lambda _name, **values: values.get("path", "")

    html = templates.env.get_template("imports/mapping.html").render(
        app_name="Booker Tee",
        command=command,
        preview=preview,
        selected_table=table,
        table_options=[table],
        compatible_table_count=14,
        mapping_templates=[],
        view=view,
    )

    assert "Настройка импорта" in html
    assert 'id="mapping-form" class="form-panel mapping-form"' in html
    assert 'onchange="this.form.submit()"' in html
    assert "table-picker" in html
    assert "choice-card" not in html
    assert "страница 1 · таблица 1" in html
    assert "Дата операции" in html
    assert "Предложение маппинга · 91%" in html
    assert "сумма: колонка 4 выбрана по заголовку" in html
    assert "Найдена только одна колонка списания/зачисления" in html
    assert 'id="posting_date_column"' in html
    assert "Дата проводки" in html
    assert 'id="balance_after_column"' in html
    assert "Остаток после" in html
    assert "Предпросмотр транзакций" in html
    assert "В предпросмотре много строк с ошибками" in html
    assert "импортировать все страницы" in html
    assert "импорт: 14 таблиц по этой схеме" in html
    assert 'form="mapping-form"' in html
    assert f"/imports/documents/{document_id}/mapping/import" in html
    assert "12.05.2026" in html
    assert "-842.00" in html
    assert "Оплата товаров по карте" in html
