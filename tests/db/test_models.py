from sqlalchemy.orm import configure_mappers

from app.features.chat_integrations.models import TelegramWebhookUpdate
from app.features.imports.models import ParseAttempt, UploadedDocument
from app.features.users.models import AuthRateLimit, User, UserSession, UserToken


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


def test_uploaded_document_tracks_source_file_deletion() -> None:
    assert UploadedDocument.__table__.c.storage_key.nullable is True
    assert UploadedDocument.__table__.c.source_file_deleted_at.nullable is True


def test_user_identity_foundation_schema_is_registered() -> None:
    assert {"email_verified_at", "deactivated_at"} <= set(User.__table__.columns.keys())
    assert "user_agent_summary" in UserSession.__table__.columns
    assert UserToken.__tablename__ == "user_tokens"
    assert AuthRateLimit.__tablename__ == "auth_rate_limits"


def test_telegram_webhook_inbox_schema_is_registered() -> None:
    assert TelegramWebhookUpdate.__tablename__ == "telegram_webhook_updates"
    assert {column.name for column in TelegramWebhookUpdate.__table__.primary_key} == {"update_id"}
