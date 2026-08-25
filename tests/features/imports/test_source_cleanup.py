import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.features.imports.documents.source_cleanup import UploadSourceCleanup
from app.features.imports.documents.types import ParseAttemptStatus, UploadedDocumentStatus
from app.features.imports.models import UploadedDocument


class DocumentsStub:
    def __init__(self, documents: list[UploadedDocument]) -> None:
        self.documents = documents
        self.list_calls = 0

    async def list_documents_with_source_file(
        self,
        *,
        after_created_at: datetime | None,
        after_id: UUID | None,
        limit: int,
    ) -> list[UploadedDocument]:
        self.list_calls += 1
        if self.list_calls > 10:
            raise AssertionError("cleanup pagination did not advance")
        documents = [document for document in self.documents if document.storage_key is not None]
        if after_created_at is not None and after_id is not None:
            documents = [
                document
                for document in documents
                if (document.created_at, document.id) > (after_created_at, after_id)
            ]
        return sorted(documents, key=lambda document: (document.created_at, document.id))[:limit]

    async def list_active_storage_keys(self) -> set[str]:
        return {
            document.storage_key for document in self.documents if document.storage_key is not None
        }


async def test_cleanup_expires_sources_reconciles_missing_and_deletes_old_orphans(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    now = datetime(2026, 8, 19, 12, tzinfo=UTC)
    settings = Settings(upload_storage_dir=tmp_path, upload_retention_hours=48)
    workspace_id = uuid4()

    def store(document_id: UUID) -> tuple[str, Path]:
        storage_key = f"{workspace_id}/{document_id}/source.pdf"
        path = tmp_path / storage_key
        path.parent.mkdir(parents=True)
        path.write_bytes(b"%PDF-1.4")
        return storage_key, path

    expired_id, missing_id, recent_id, retry_id = uuid4(), uuid4(), uuid4(), uuid4()
    visual_recent_id, visual_expired_id, visual_terminal_id = uuid4(), uuid4(), uuid4()
    expired_key, expired_path = store(expired_id)
    recent_key, recent_path = store(recent_id)
    retry_key, retry_path = store(retry_id)
    visual_recent_key, visual_recent_path = store(visual_recent_id)
    visual_expired_key, visual_expired_path = store(visual_expired_id)
    visual_terminal_key, visual_terminal_path = store(visual_terminal_id)
    missing_key = f"{workspace_id}/{missing_id}/source.pdf"
    documents = [
        cast(
            UploadedDocument,
            SimpleNamespace(
                id=expired_id,
                status=UploadedDocumentStatus.REQUIRES_REVIEW,
                created_at=now - timedelta(hours=49),
                storage_key=expired_key,
                source_file_deleted_at=None,
                parse_attempts=[],
            ),
        ),
        cast(
            UploadedDocument,
            SimpleNamespace(
                id=missing_id,
                status=UploadedDocumentStatus.REQUIRES_REVIEW,
                created_at=now - timedelta(hours=2),
                storage_key=missing_key,
                source_file_deleted_at=None,
                parse_attempts=[],
            ),
        ),
        cast(
            UploadedDocument,
            SimpleNamespace(
                id=recent_id,
                status=UploadedDocumentStatus.REQUIRES_REVIEW,
                created_at=now - timedelta(hours=1),
                storage_key=recent_key,
                source_file_deleted_at=None,
                parse_attempts=[],
            ),
        ),
        cast(
            UploadedDocument,
            SimpleNamespace(
                id=retry_id,
                status=UploadedDocumentStatus.PARSED,
                created_at=now - timedelta(hours=1),
                storage_key=retry_key,
                source_file_deleted_at=None,
                parse_attempts=[
                    SimpleNamespace(
                        status=ParseAttemptStatus.SUCCESS,
                        validation_report_json=None,
                    )
                ],
            ),
        ),
        cast(
            UploadedDocument,
            SimpleNamespace(
                id=visual_recent_id,
                status=UploadedDocumentStatus.REQUIRES_REVIEW,
                created_at=now - timedelta(hours=1),
                storage_key=visual_recent_key,
                source_file_deleted_at=None,
                parse_attempts=[
                    SimpleNamespace(
                        status=ParseAttemptStatus.SUCCESS,
                        validation_report_json={
                            "status": "valid",
                            "source": "visual_coordinate_mapping",
                        },
                    )
                ],
            ),
        ),
        cast(
            UploadedDocument,
            SimpleNamespace(
                id=visual_expired_id,
                status=UploadedDocumentStatus.REQUIRES_REVIEW,
                created_at=now - timedelta(hours=49),
                storage_key=visual_expired_key,
                source_file_deleted_at=None,
                parse_attempts=[
                    SimpleNamespace(
                        status=ParseAttemptStatus.SUCCESS,
                        validation_report_json={
                            "status": "valid",
                            "source": "visual_coordinate_mapping",
                        },
                    )
                ],
            ),
        ),
        cast(
            UploadedDocument,
            SimpleNamespace(
                id=visual_terminal_id,
                status=UploadedDocumentStatus.IMPORTED,
                created_at=now - timedelta(hours=1),
                storage_key=visual_terminal_key,
                source_file_deleted_at=None,
                parse_attempts=[
                    SimpleNamespace(
                        status=ParseAttemptStatus.SUCCESS,
                        validation_report_json={
                            "status": "valid",
                            "source": "visual_coordinate_mapping",
                        },
                    )
                ],
            ),
        ),
    ]
    old_orphan_key, old_orphan_path = store(uuid4())
    _, fresh_orphan_path = store(uuid4())
    old_timestamp = (now - timedelta(hours=49)).timestamp()
    os.utime(old_orphan_path, (old_timestamp, old_timestamp))

    commit = AsyncMock()
    cleanup = UploadSourceCleanup(
        cast(AsyncSession, SimpleNamespace(commit=commit)),
        settings,
    )
    cleanup.documents = cast(Any, DocumentsStub(documents))
    scrub_states = AsyncMock(return_value=2)
    cleanup.chat_integrations = cast(
        Any,
        SimpleNamespace(scrub_terminal_upload_state_payloads=scrub_states),
    )

    result = await cleanup.run(now=now, batch_size=2)

    assert result.scanned_documents == 7
    assert result.source_deleted == 4
    assert result.missing_reconciled == 1
    assert result.orphan_deleted == 1
    assert result.telegram_states_scrubbed == 2
    assert result.failures == 0
    assert documents[0].storage_key is None
    assert documents[0].source_file_deleted_at == now
    assert documents[1].storage_key is None
    assert documents[1].source_file_deleted_at == now
    assert documents[2].storage_key == recent_key
    assert documents[3].storage_key is None
    assert documents[4].storage_key == visual_recent_key
    assert documents[5].storage_key is None
    assert documents[6].storage_key is None
    assert not expired_path.exists()  # noqa: ASYNC240
    assert recent_path.exists()  # noqa: ASYNC240
    assert not retry_path.exists()  # noqa: ASYNC240
    assert visual_recent_path.exists()  # noqa: ASYNC240
    assert not visual_expired_path.exists()  # noqa: ASYNC240
    assert not visual_terminal_path.exists()  # noqa: ASYNC240
    assert not (tmp_path / old_orphan_key).exists()  # noqa: ASYNC240
    assert fresh_orphan_path.exists()  # noqa: ASYNC240
    assert commit.await_count == 5
    scrub_states.assert_awaited_once_with(now=now)

    def fail_orphan_scan(*_args: object, **_kwargs: object) -> list[str]:
        raise PermissionError("sensitive path")

    cleanup.storage = cast(
        Any,
        SimpleNamespace(find_orphan_storage_keys=fail_orphan_scan),
    )
    assert await cleanup._delete_orphans(set(), cutoff=now, batch_size=2) == (0, 1)
    assert "PermissionError" in caplog.text
    assert "sensitive path" not in caplog.text
