from sqlalchemy.orm import configure_mappers

from app.features.imports.models import ParseAttempt, UploadedDocument


def test_sqlalchemy_mappers_are_configured() -> None:
    configure_mappers()


def test_uploaded_document_children_are_deleted_with_document() -> None:
    parse_attempts = UploadedDocument.parse_attempts.property
    raw_transactions = UploadedDocument.raw_transactions.property
    attempt_raw_transactions = ParseAttempt.raw_transactions.property

    assert "delete-orphan" in parse_attempts.cascade
    assert "delete-orphan" in raw_transactions.cascade
    assert "delete-orphan" in attempt_raw_transactions.cascade
    assert parse_attempts.passive_deletes is True
    assert raw_transactions.passive_deletes is True
    assert attempt_raw_transactions.passive_deletes is True
