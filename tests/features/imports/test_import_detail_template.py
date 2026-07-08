from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

from app.features.accounts.models import AccountType
from app.features.imports.application.documents.detail_view import (
    ImportAccountRef,
    ImportDocumentDetailView,
    ImportParseAttemptView,
    ImportRawTransactionRow,
)
from app.features.imports.application.unknown_statement_mappings.dto import (
    UnknownStatementMappedRow,
    UnknownStatementMappingCommand,
    UnknownStatementMappingPreview,
    UnknownStatementMappingWarning,
)
from app.features.imports.application.unknown_statement_mappings.template_commands import (
    mapping_command_as_json,
)
from app.features.imports.models import (
    ImportMappingTemplate,
    ParseAttemptStatus,
    RawTransactionStatus,
    UploadedDocumentStatus,
)
from app.features.imports.presentation.document_page.presenter import DocumentDetailPresenter
from app.features.imports.presentation.mapping.form import mapping_form
from app.features.imports.presentation.mapping.models import (
    MappingDocumentVM,
    MappingNextStepVM,
    MappingTemplateNoticeVM,
)
from app.features.imports.presentation.mapping.page import MappingPagePresenter
from app.features.imports.presentation.mapping.preview import (
    mapping_import_action,
    mapping_preview_rows,
    mapping_preview_summary,
    mapping_submit_actions,
    mapping_warnings,
)
from app.features.imports.presentation.mapping.tables import (
    mapping_selected_table_vm,
    mapping_table_picker_options,
)
from app.templating import create_templates


def render_import_detail(view: ImportDocumentDetailView, *, can_manage_imports: bool = True) -> str:
    templates = create_templates()
    cast(Any, templates.env.globals)["url_for"] = lambda _name, **values: values.get("path", "")
    return templates.env.get_template("imports/detail.html").render(
        app_name="Booker Tee",
        page=DocumentDetailPresenter().build(
            view,
            can_manage_imports=can_manage_imports,
        ),
    )


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
    html = render_import_detail(view)

    assert "ВТБ вклад" in html
    assert "депозит" in html
    assert "RUB" in html
    assert "import-more-actions" in html
    assert "import-action-details__summary" in html
    assert "details-toggle-open" in html
    assert "details-toggle-close" in html
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
    html = render_import_detail(view)

    assert "document-detail-grid" in html
    assert "empty-state" in html
    assert "Сырые строки не извлечены" in html
    assert "Загрузите другую выписку" in html
    assert 'class="import-parse-history" open' in html
    assert "история парсинга" in html
    assert "1 попытка" in html
    assert "parse-attempt-list" in html
    assert "parse-attempt-card" in html
    assert "Отладочные данные документа" in html
    assert "Технические детали" not in html
    assert f"ID {document_id}" in html
    assert f"ID {attempt_id}" in html
    assert "PdfminerException: No /Root object!" in html
    assert f'<td class="status">{attempt_id}</td>' not in html


def test_import_detail_raw_transactions_use_review_like_topline_and_ru_date() -> None:
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
    html = render_import_detail(view)

    assert "financial-row financial-row--single raw-transaction-card import-raw-row" in html
    assert "financial-row__date raw-transaction-date import-raw-row__date" in html
    assert "financial-row__amount raw-transaction-amount import-raw-row__amount" in html
    assert "financial-row__description entry-description import-raw-row__description" in html
    assert "raw-transaction-head" in html
    assert "import-raw-row__topline" in html
    assert "import-raw-row__amount" in html
    assert "26.05.2026" in html
    assert "2026-05-26" not in html
    assert "Технические детали</summary>" not in html
    assert "ID строки" in html
    assert html.index("#0") < html.index("26.05.2026")
    assert html.index("26.05.2026") < html.index("-2509.00")
    assert html.index("нормализовано") < html.index("-2509.00")


def test_import_detail_template_shows_unknown_statement_mapping_preview() -> None:
    document_id = uuid4()
    attempt_id = uuid4()
    validation: dict[str, object] = {
        "status": "needs_mapping",
        "message": (
            "Parser is not available for this statement yet, but transaction-like tables "
            "were extracted. Configure column mapping to import it."
        ),
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
    html = render_import_detail(view)

    assert "Нужна настройка импорта" in html
    assert "Строки появятся после настройки" in html
    assert "Выберите таблицу и колонки" in html
    assert "import-parse-history" in html
    assert 'class="import-parse-history" open' not in html
    assert "Ozon Bank" in html
    assert "карточная выписка" in html
    assert "текстовый" in html
    assert "Предпросмотр таблиц" in html
    assert "mapping-preview-card" in html
    assert "mapping-preview-table" in html
    assert "Предложение маппинга · 91%" in html
    assert "дата: колонка 1 выбрана по заголовку" in html
    assert "дата: колонка 1 · Дата операции" in html
    assert "сумма: колонка 4 · Сумма операции" in html
    assert "Для этой выписки пока нет готового парсера" in html
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
    document = MappingDocumentVM(
        status_label="требует проверки",
        filename=view.original_filename,
        detail_url=f"/imports/documents/{view.id}",
        preview_url=f"/imports/documents/{view.id}/mapping",
        import_url=f"/imports/documents/{view.id}/mapping/import",
    )
    selected_table_vm = mapping_selected_table_vm(table, compatible_table_count=14)
    import_action = mapping_import_action(
        document=document,
        compatible_table_count=14,
    )

    html = templates.env.get_template("imports/mapping.html").render(
        app_name="Booker Tee",
        page=SimpleNamespace(
            document=document,
            next_step=MappingNextStepVM(
                title="Импортируйте строки",
                message=(
                    "Предпросмотр готов. После импорта строки попадут в проверку, "
                    "но еще не станут подтвержденным учетом."
                ),
                primary_href="#mapping-import-actions",
                primary_label="к импорту строк",
                primary_icon="import",
            ),
            template_notice=None,
            form=mapping_form(command, selected_table_vm.column_options),
            has_preview=True,
            warnings=mapping_warnings(preview),
            form_actions=mapping_submit_actions(
                document=document,
                import_action=import_action,
                preview_ready=True,
            ),
            preview_summary=mapping_preview_summary(preview),
            preview_rows=mapping_preview_rows(preview),
            selected_table_vm=selected_table_vm,
            table_picker_options=mapping_table_picker_options([table], command),
        ),
    )

    assert "Настройка импорта" in html
    assert 'id="mapping-form" class="form-panel mapping-form"' in html
    assert 'onchange="this.form.submit()"' in html
    assert "table-picker" in html
    assert "choice-card" not in html
    assert "страница 1 · таблица 1" in html
    assert "mapping-selected-table" in html
    assert "mapping-selected-table__signals" in html
    assert "ui-signal-list" in html
    assert "review-flags" not in html
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
    assert "обновить предпросмотр" in html
    assert "mapping-action-row__button--secondary" in html
    assert "mapping-action-row__button--primary" in html
    assert "импортировать все страницы" in html
    assert "импорт: 14 таблиц по этой схеме" in html
    assert 'form="mapping-form"' in html
    assert "mapping-preview-row__topline" in html
    assert "mapping-preview-row__error" not in html
    assert f"/imports/documents/{document_id}/mapping/import" in html
    assert "12.05.2026" in html
    assert "-842.00" in html
    assert "Оплата товаров по карте" in html


def test_mapping_warning_presentation_handles_known_and_unknown_codes() -> None:
    preview = UnknownStatementMappingPreview(
        rows=[],
        warnings=[
            UnknownStatementMappingWarning(
                code="duplicate_column_roles",
                severity="warning",
                fields=["operation_date", "amount"],
            ),
            UnknownStatementMappingWarning(
                code="unknown_warning",
                severity="warning",
            ),
        ],
    )

    warnings = mapping_warnings(preview)

    assert warnings[0].message == (
        "Одна колонка выбрана для нескольких ролей. Проверьте поля: operation_date, amount."
    )
    assert warnings[0].severity == "warning"
    assert warnings[1].message == "unknown_warning"


def test_mapping_import_action_presentation_matches_preview_scope() -> None:
    document = MappingDocumentVM(
        status_label="требует проверки",
        filename="statement.pdf",
        detail_url="/imports/documents/document-id",
        preview_url="/imports/documents/document-id/mapping",
        import_url="/imports/documents/document-id/mapping/import",
    )

    single_table_action = mapping_import_action(
        document=document,
        compatible_table_count=1,
    )
    multi_table_action = mapping_import_action(
        document=document,
        compatible_table_count=14,
    )

    assert (
        mapping_import_action(
            document=document,
            compatible_table_count=0,
        )
        is None
    )
    assert single_table_action is not None
    assert single_table_action.label == "импортировать строки"
    assert single_table_action.form_action == "/imports/documents/document-id/mapping/import"
    assert multi_table_action is not None
    assert multi_table_action.label == "импортировать все страницы"


def test_mapping_submit_actions_make_import_primary_after_preview() -> None:
    document = MappingDocumentVM(
        status_label="требует проверки",
        filename="statement.pdf",
        detail_url="/imports/documents/document-id",
        preview_url="/imports/documents/document-id/mapping",
        import_url="/imports/documents/document-id/mapping/import",
    )

    import_action = mapping_import_action(
        document=document,
        compatible_table_count=1,
    )
    preview_actions = mapping_submit_actions(
        document=document,
        import_action=import_action,
        preview_ready=False,
    )
    import_actions = mapping_submit_actions(
        document=document,
        import_action=import_action,
        preview_ready=True,
    )

    assert [(action.label, action.tone) for action in preview_actions] == [
        ("показать предпросмотр", "primary"),
        ("импортировать строки", "secondary"),
    ]
    assert [(action.label, action.tone) for action in import_actions] == [
        ("обновить предпросмотр", "secondary"),
        ("импортировать строки", "primary"),
    ]


def test_mapping_preview_summary_presentation_counts_rows() -> None:
    preview = UnknownStatementMappingPreview(
        rows=[
            UnknownStatementMappedRow(
                page_number=1,
                table_index=0,
                source_row_number=1,
                operation_date_raw="12.05.2026",
                operation_date=date(2026, 5, 12),
                description_raw="Оплата товаров",
                description="Оплата товаров",
                amount_raw="-842,00",
                amount=Decimal("-842.00"),
                currency_raw="RUB",
                currency="RUB",
                status="valid",
                error="",
            ),
            UnknownStatementMappedRow(
                page_number=1,
                table_index=0,
                source_row_number=2,
                operation_date_raw="",
                operation_date=None,
                description_raw="",
                description=None,
                amount_raw="",
                amount=None,
                currency_raw="RUB",
                currency="RUB",
                status="error",
                error="missing date",
            ),
        ]
    )

    summary = mapping_preview_summary(preview)

    assert summary is not None
    assert [metric.label for metric in summary.metrics] == ["строки", "готово", "ошибки"]
    assert [metric.value for metric in summary.metrics] == [2, 1, 1]
    assert [metric.class_name for metric in summary.metrics] == [
        "metric",
        "metric metric-income",
        "metric metric-expense",
    ]
    assert mapping_preview_summary(None) is None


def test_mapping_preview_rows_prepare_display_values() -> None:
    preview = UnknownStatementMappingPreview(
        rows=[
            UnknownStatementMappedRow(
                page_number=1,
                table_index=0,
                source_row_number=1,
                operation_date_raw="12.05.2026 15:42:10",
                operation_date=date(2026, 5, 12),
                posting_date_raw="13.05.2026",
                posting_date=None,
                description_raw="raw description",
                description="clean description",
                amount_raw="-842,00 ₽",
                amount=Decimal("-842.00"),
                currency_raw="RUB",
                currency="RUB",
                status="valid",
                error="",
            ),
            UnknownStatementMappedRow(
                page_number=1,
                table_index=0,
                source_row_number=2,
                operation_date_raw="bad date",
                operation_date=None,
                description_raw="raw only",
                description=None,
                amount_raw="not parsed",
                amount=None,
                currency_raw="RUB",
                currency="RUB",
                status="error",
                error="missing amount",
            ),
        ]
    )

    rows = mapping_preview_rows(preview)

    assert rows[0].source_row_number == 1
    assert rows[0].status_label == "корректно"
    assert rows[0].status_badge_class == "badge-valid"
    assert rows[0].operation_date == "12.05.2026"
    assert rows[0].posting_date == "13.05.2026"
    assert rows[0].amount == "-842.00"
    assert rows[0].amount_class == "amount amount-expense"
    assert rows[0].description == "clean description"
    assert rows[1].status_label == "ошибка"
    assert rows[1].operation_date == "bad date"
    assert rows[1].amount == "not parsed"
    assert rows[1].amount_class == "amount"
    assert rows[1].description == "raw only"
    assert mapping_preview_rows(None) == []


def test_mapping_selected_table_prepares_suggestions_and_candidates() -> None:
    table = {
        "page_number": 1,
        "table_index": 0,
        "row_count": 2,
        "column_count": 4,
        "rows": [
            ["Дата операции", "Описание", "Документ", "Сумма операции"],
            ["12.05.2026", "Оплата товаров", "1", "-842,00 ₽"],
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
                "confidence": 0.91,
                "reasons": [
                    {
                        "field": "operation_date",
                        "column_index": 0,
                        "header": "Дата операции",
                        "evidence": "header_match",
                    },
                    {
                        "field": "amount",
                        "column_index": 3,
                        "evidence": "money_like_values",
                        "matched_count": 2,
                        "sample_count": 3,
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

    selected_table = mapping_selected_table_vm(table, compatible_table_count=1)

    assert selected_table.mapping_suggestion is not None
    assert selected_table.mapping_suggestion.title == "Предложение маппинга · 91%"
    assert [reason.message for reason in selected_table.mapping_suggestion.reasons] == [
        "дата: колонка 1 выбрана по заголовку «Дата операции».",
        "сумма: колонка 4 содержит 2/3 значений, похожих на суммы.",
    ]
    assert [warning.message for warning in selected_table.mapping_suggestion.warnings] == [
        "Найдена только одна колонка списания/зачисления. Проверьте знак суммы перед импортом."
    ]
    assert [candidate.message for candidate in selected_table.column_candidates] == [
        "дата: колонка 1 · Дата операции"
    ]
    assert [row.cells for row in selected_table.rows] == [
        ["Дата операции", "Описание", "Документ", "Сумма операции"],
        ["12.05.2026", "Оплата товаров", "1", "-842,00 ₽"],
    ]


def test_mapping_form_prepares_selected_fields() -> None:
    column_options = mapping_selected_table_vm(
        {
            "page_number": 1,
            "table_index": 0,
            "row_count": 2,
            "column_count": 4,
            "rows": [
                ["Дата операции", "Описание", "Документ", "Сумма операции"],
                ["12.05.2026", "Оплата товаров", "1", "-842,00 ₽"],
            ],
        },
        compatible_table_count=1,
    ).column_options
    command = UnknownStatementMappingCommand(
        page_number=1,
        table_index=0,
        operation_date_column=0,
        posting_date_column=None,
        description_column=1,
        amount_column=3,
        debit_amount_column=None,
        credit_amount_column=None,
        currency_column=None,
        balance_after_column=None,
        first_data_row=1,
        default_currency="RUB",
    )

    form = mapping_form(command, column_options)
    fields = {field.name: field for field in form.select_fields}

    assert [field.name for field in form.select_fields] == [
        "operation_date_column",
        "posting_date_column",
        "description_column",
        "amount_column",
        "debit_amount_column",
        "credit_amount_column",
        "currency_column",
        "balance_after_column",
    ]
    assert fields["operation_date_column"].options[0].is_selected is True
    assert fields["posting_date_column"].options[0].value == "-1"
    assert fields["posting_date_column"].options[0].is_selected is True
    assert fields["amount_column"].options[0].label == "нет единой колонки"
    assert fields["amount_column"].options[0].is_selected is False
    assert [option.value for option in fields["amount_column"].options if option.is_selected] == [
        "3"
    ]
    assert form.first_data_row.value == "1"
    assert form.first_data_row.min_value == "0"
    assert form.default_currency.value == "RUB"


def test_mapping_page_context_prepares_document_contract() -> None:
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
        validation={"status": "needs_mapping", "table_previews": []},
    )

    page_context = MappingPagePresenter().build(
        view=view,
        default_currency="RUB",
        mapping_templates=[],
    )
    values = page_context.template_values(app_name="Booker Tee", workspace=object())

    assert "view" not in values
    assert "command" not in values
    assert "preview" not in values
    assert "selected_table" not in values
    assert "table_options" not in values
    assert "compatible_table_count" not in values
    assert "mapping_next_step" not in values
    assert "mapping_form" not in values
    assert "mapping_templates" not in values
    assert page_context.document.status_label == "требует проверки"
    assert page_context.document.filename == "ozonbank_card_statement.pdf"
    assert page_context.document.detail_url == f"/imports/documents/{document_id}"
    assert page_context.document.preview_url == f"/imports/documents/{document_id}/mapping"
    assert page_context.document.import_url == f"/imports/documents/{document_id}/mapping/import"
    assert page_context.next_step.title == "Вернитесь к документу"
    assert page_context.next_step.primary_href == f"/imports/documents/{document_id}"
    assert page_context.next_step.secondary_href == "/imports/upload"
    assert values["page"] == page_context


def test_mapping_template_notice_hides_template_model_from_template() -> None:
    document_id = uuid4()
    command = UnknownStatementMappingCommand(
        page_number=1,
        table_index=0,
        operation_date_column=0,
        posting_date_column=None,
        description_column=2,
        amount_column=3,
        debit_amount_column=None,
        credit_amount_column=None,
        currency_column=4,
        balance_after_column=None,
        first_data_row=1,
        default_currency="RUB",
    )
    raw_tables: list[dict[str, object]] = [
        {
            "page_number": 1,
            "tables": [
                [
                    ["Дата операции", "Документ", "Описание", "Сумма операции", "Валюта"],
                    ["12.05.2026 15:42:10", "1", "Оплата товаров", "-842,00 ₽", "RUB"],
                ]
            ],
        }
    ]
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
                id=uuid4(),
                status=ParseAttemptStatus.SUCCESS,
                parser_name="unknown_statement",
                parser_version=None,
                started_at=datetime(2026, 5, 12, 10, 0),
                finished_at=datetime(2026, 5, 12, 10, 1),
                error_message=None,
                validation_report=None,
                raw_tables=raw_tables,
                raw_text_by_page=None,
            )
        ],
        validation={"status": "needs_mapping", "table_previews": []},
    )

    page_context = MappingPagePresenter().build(
        view=view,
        default_currency="RUB",
        mapping_templates=[
            ImportMappingTemplate(
                name="Ozon Bank карта",
                bank_name="Ozon Bank",
                statement_type="card_statement",
                default_currency="RUB",
                column_mapping_json=mapping_command_as_json(command, raw_tables=raw_tables),
            )
        ],
    )

    assert page_context.template_notice == MappingTemplateNoticeVM(
        title="Найден шаблон",
        message=(
            "Ozon Bank карта. Поля ниже уже заполнены из последнего подходящего "
            "шаблона для этого банка и типа выписки."
        ),
    )
