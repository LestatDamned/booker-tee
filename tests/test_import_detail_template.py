from datetime import datetime
from typing import Any, cast
from uuid import uuid4

from app.features.accounts.models import AccountType
from app.features.imports.dto import (
    ImportAccountRef,
    ImportDocumentDetailView,
    ImportParseAttemptView,
)
from app.features.imports.models import ParseAttemptStatus, UploadedDocumentStatus
from app.templating import create_templates


def test_import_detail_template_shows_readable_account_reference() -> None:
    account_id = uuid4()
    view = ImportDocumentDetailView(
        id=uuid4(),
        original_filename="statement.pdf",
        status=UploadedDocumentStatus.PARSED,
        sha256_hash="a" * 64,
        storage_key="workspace/document/statement.pdf",
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
    assert f"ID {str(account_id)[:8]}" in html
    assert f">{account_id}<" not in html


def test_import_detail_template_keeps_failed_parse_page_compact() -> None:
    document_id = uuid4()
    attempt_id = uuid4()
    view = ImportDocumentDetailView(
        id=document_id,
        original_filename="broken.pdf",
        status=UploadedDocumentStatus.FAILED_TO_PARSE,
        sha256_hash="831fb532af945a1753654723284f16983acd3e245d6b82d77e5ac9cd1c65efa3",
        storage_key=f"workspace/{document_id}/broken.pdf",
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
    assert "parse-attempt-list" in html
    assert "parse-attempt-card" in html
    assert f"ID {str(document_id)[:8]}" in html
    assert f"ID {str(attempt_id)[:8]}" in html
    assert "PdfminerException: No /Root object!" in html
    assert f'<td class="status">{attempt_id}</td>' not in html
