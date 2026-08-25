import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.settings import Settings
from app.db import model_registry as model_registry  # noqa: F401
from app.db.base import utc_now
from app.db.session import session_factory
from app.features.chat_integrations.repository import ChatIntegrationRepository
from app.features.imports.documents.commands.upload import should_retain_source_file
from app.features.imports.documents.errors import UploadValidationError
from app.features.imports.documents.repository import DocumentRepository
from app.features.imports.documents.storage import UploadStorage
from app.features.imports.documents.types import UploadedDocumentStatus
from app.features.imports.models import UploadedDocument

logger = logging.getLogger(__name__)
DEFAULT_CLEANUP_BATCH_SIZE = 100


@dataclass(frozen=True)
class UploadSourceCleanupResult:
    scanned_documents: int = 0
    source_deleted: int = 0
    missing_reconciled: int = 0
    orphan_deleted: int = 0
    telegram_states_scrubbed: int = 0
    failures: int = 0


class UploadSourceCleanup:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.documents = DocumentRepository(session)
        self.chat_integrations = ChatIntegrationRepository(session)
        self.storage = UploadStorage(settings.upload_storage_dir)

    async def run(
        self,
        *,
        now: datetime | None = None,
        batch_size: int = DEFAULT_CLEANUP_BATCH_SIZE,
    ) -> UploadSourceCleanupResult:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        current_time = now or utc_now()
        cutoff = current_time - timedelta(hours=self.settings.upload_retention_hours)
        scanned = deleted = missing = failures = 0
        cursor_created_at: datetime | None = None
        cursor_id: UUID | None = None

        while documents := await self.documents.list_documents_with_source_file(
            after_created_at=cursor_created_at,
            after_id=cursor_id,
            limit=batch_size,
        ):
            for document in documents:
                scanned += 1
                outcome = await self._cleanup_document(document, cutoff, current_time)
                if outcome == "deleted":
                    deleted += 1
                elif outcome == "missing":
                    missing += 1
                elif outcome == "failed":
                    failures += 1
            cursor_created_at = documents[-1].created_at
            cursor_id = documents[-1].id
            await self.session.commit()

        referenced_keys = await self.documents.list_active_storage_keys()
        telegram_states_scrubbed = (
            await self.chat_integrations.scrub_terminal_upload_state_payloads(now=current_time)
        )
        await self.session.commit()
        orphan_deleted, orphan_failures = await self._delete_orphans(
            referenced_keys,
            cutoff=cutoff,
            batch_size=batch_size,
        )
        return UploadSourceCleanupResult(
            scanned_documents=scanned,
            source_deleted=deleted,
            missing_reconciled=missing,
            orphan_deleted=orphan_deleted,
            telegram_states_scrubbed=telegram_states_scrubbed,
            failures=failures + orphan_failures,
        )

    async def _cleanup_document(
        self,
        document: UploadedDocument,
        cutoff: datetime,
        deleted_at: datetime,
    ) -> str:
        storage_key = document.storage_key
        if storage_key is None:
            return "unchanged"
        try:
            source_exists = self.storage.storage_key_exists(storage_key)
            latest_attempt = document.parse_attempts[0] if document.parse_attempts else None
            retain_until_cutoff = latest_attempt is None or (
                should_retain_source_file(latest_attempt)
                and (
                    (latest_attempt.validation_report_json or {}).get("source")
                    != "visual_coordinate_mapping"
                    or document.status is UploadedDocumentStatus.REQUIRES_REVIEW
                )
            )
            if source_exists and retain_until_cutoff and document.created_at > cutoff:
                return "unchanged"
            if source_exists:
                await self.storage.delete_storage_key(storage_key)
                outcome = "deleted"
            else:
                outcome = "missing"
        except (OSError, UploadValidationError) as error:
            log_cleanup_failure(error)
            return "failed"

        document.storage_key = None
        document.source_file_deleted_at = deleted_at
        return outcome

    async def _delete_orphans(
        self,
        referenced_keys: set[str],
        *,
        cutoff: datetime,
        batch_size: int,
    ) -> tuple[int, int]:
        deleted = failures = 0
        try:
            orphan_keys = self.storage.find_orphan_storage_keys(
                referenced_keys,
                older_than=cutoff,
                limit=batch_size,
            )
        except (OSError, UploadValidationError) as error:
            log_cleanup_failure(error)
            return 0, 1
        for storage_key in orphan_keys:
            try:
                await self.storage.delete_storage_key(storage_key)
            except (OSError, UploadValidationError) as error:
                failures += 1
                log_cleanup_failure(error)
            else:
                deleted += 1
        return deleted, failures


def log_cleanup_failure(error: Exception) -> None:
    logger.warning("Upload source cleanup failed error_type=%s", type(error).__name__)


async def run_upload_source_cleanup() -> UploadSourceCleanupResult:
    settings = get_settings()
    settings.validate_for_runtime()
    async with session_factory() as session:
        return await UploadSourceCleanup(session, settings).run()


def main() -> None:
    result = asyncio.run(run_upload_source_cleanup())
    status = "ok" if result.failures == 0 else "partial_failure"
    print(
        f"Upload source cleanup status={status} "
        f"scanned={result.scanned_documents} "
        f"source_deleted={result.source_deleted} "
        f"missing_reconciled={result.missing_reconciled} "
        f"orphan_deleted={result.orphan_deleted} "
        f"telegram_states_scrubbed={result.telegram_states_scrubbed} "
        f"failures={result.failures}"
    )
    if result.failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
