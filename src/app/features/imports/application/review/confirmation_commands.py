from dataclasses import dataclass
from hashlib import sha256
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.imports.application.documents.status import ImportedDocumentStatusUpdater
from app.features.imports.application.review.classification import (
    build_import_review_draft_evaluation,
)
from app.features.imports.application.review.validation_refresh import (
    refresh_document_validation,
)
from app.features.imports.domain.review_confirmability import ReviewBlockingReasonCode
from app.features.imports.domain.types import RawTransactionStatus
from app.features.imports.errors import RawTransactionReviewError
from app.features.imports.repository import ImportRepository
from app.features.ledger.application.raw_transaction_posting import RawTransactionPoster
from app.features.ledger.domain.types import OperationStatus, OperationType
from app.features.ledger.errors import LedgerPostingError, RawTransactionDedupeConflictError
from app.features.ledger.repository import LedgerRepository
from app.features.transaction_rules.application.rule_application import (
    TransactionRuleApplicationUseCase,
)
from app.features.transaction_rules.application.rule_management import (
    TransactionRuleManagementUseCase,
)
from app.features.workspaces.service import WorkspaceContext


class ImportReviewConfirmationError(ValueError):
    pass


class ImportReviewConfirmationConflictError(ImportReviewConfirmationError):
    pass


class ImportReviewConfirmationValidationError(ImportReviewConfirmationError):
    def __init__(
        self,
        *,
        blocking_reason_codes: tuple[ReviewBlockingReasonCode, ...] = (),
        field_errors: dict[str, list[str]] | None = None,
    ) -> None:
        super().__init__("Import review confirmation is not valid.")
        self.blocking_reason_codes = blocking_reason_codes
        self.field_errors = field_errors or {}


@dataclass(frozen=True)
class ConfirmImportReviewItemCommand:
    document_id: UUID
    item_id: UUID
    operation_type: OperationType
    category_id: UUID
    property_id: UUID | None
    expected_status: RawTransactionStatus
    remember_rule: bool
    rule_pattern: str | None
    idempotency_key: UUID


@dataclass(frozen=True)
class ImportReviewConfirmationResult:
    document_id: UUID
    item_id: UUID
    operation_id: UUID
    updated_item_ids: frozenset[UUID]
    replayed: bool


class ImportReviewConfirmationService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._imports = ImportRepository(session)
        self._ledger = LedgerRepository(session)
        self._poster = RawTransactionPoster(session)
        self._rules = TransactionRuleManagementUseCase(session)
        self._rule_application = TransactionRuleApplicationUseCase(session)

    async def execute(
        self,
        *,
        context: WorkspaceContext,
        command: ConfirmImportReviewItemCommand,
    ) -> ImportReviewConfirmationResult:
        try:
            row = await self._imports.get_raw_transaction_for_workspace(
                context.workspace.id,
                command.document_id,
                command.item_id,
            )
            if row is None:
                raise RawTransactionReviewError("Raw transaction row was not found.")

            replay = await self._find_replay(context=context, command=command)
            if replay is not None:
                await self._session.commit()
                return replay
            document = await self._imports.get_document_for_workspace_for_update(
                context.workspace.id,
                command.document_id,
            )
            if document is None:
                raise RawTransactionReviewError("Document was not found.")
            if row.linked_operation_id is not None or row.status is RawTransactionStatus.CONFIRMED:
                raise ImportReviewConfirmationConflictError(
                    "Raw transaction row is already linked to an operation."
                )
            if row.status is not command.expected_status:
                raise ImportReviewConfirmationConflictError("Raw transaction status has changed.")
            if command.operation_type not in {OperationType.INCOME, OperationType.EXPENSE}:
                raise ImportReviewConfirmationValidationError(
                    field_errors={
                        "operationType": ["Через confirm можно провести только доход или расход."]
                    }
                )
            if command.remember_rule and not (command.rule_pattern or "").strip():
                raise ImportReviewConfirmationValidationError(
                    field_errors={
                        "rulePattern": ["Укажите текст, по которому определять похожие строки."]
                    }
                )

            category = await self._poster.references.get_required_import_category(
                context.workspace.id,
                command.category_id,
            )
            property_ = await self._poster.references.get_property(
                context.workspace.id,
                command.property_id,
            )
            evaluation = build_import_review_draft_evaluation(
                document=document,
                row=row,
                explicit_operation_type=command.operation_type,
                category_id=category.id,
                property_id=property_.id if property_ is not None else None,
                category_is_uncategorized=category.system_key == "uncategorized",
            )
            if not evaluation.confirmability.can_confirm:
                raise ImportReviewConfirmationValidationError(
                    blocking_reason_codes=evaluation.confirmability.blocking_reason_codes,
                )
            if row.dedupe_hash is not None and (
                await self._imports.has_confirmed_raw_transaction_with_dedupe_hash(
                    workspace_id=context.workspace.id,
                    dedupe_hash=row.dedupe_hash,
                    exclude_raw_transaction_id=row.id,
                )
            ):
                raise ImportReviewConfirmationConflictError(
                    "A confirmed raw transaction already uses this dedupe hash."
                )

            operation = await self._poster.post_raw_transaction(
                context=context,
                document_id=command.document_id,
                raw_transaction_id=command.item_id,
                category_id=command.category_id,
                property_id=command.property_id,
                idempotency_key=command.idempotency_key,
                idempotency_fingerprint=self._fingerprint(command),
            )
            updated_item_ids: set[UUID] = {command.item_id}
            if command.remember_rule:
                await self._rules.create_rule_from_raw_confirmation(
                    context=context,
                    document_id=command.document_id,
                    raw_transaction_id=command.item_id,
                    category_id=command.category_id,
                    property_id=command.property_id,
                    pattern=command.rule_pattern,
                )
                summary = await self._rule_application.apply_rules_to_document(
                    workspace_id=context.workspace.id,
                    document_id=command.document_id,
                )
                updated_item_ids.update(summary.updated_raw_transaction_ids)
            await refresh_document_validation(self._imports, document)
            await ImportedDocumentStatusUpdater(self._imports).sync_review_status(document)
            await self._session.commit()
            return ImportReviewConfirmationResult(
                document_id=command.document_id,
                item_id=command.item_id,
                operation_id=operation.id,
                updated_item_ids=frozenset(updated_item_ids),
                replayed=False,
            )
        except IntegrityError as exc:
            await self._session.rollback()
            replay = await self._find_replay(context=context, command=command)
            if replay is not None:
                return replay
            raise ImportReviewConfirmationConflictError(
                "Import review confirmation conflicts with committed data."
            ) from exc
        except RawTransactionDedupeConflictError as exc:
            await self._session.rollback()
            raise ImportReviewConfirmationConflictError(str(exc)) from exc
        except LedgerPostingError as exc:
            await self._session.rollback()
            raise ImportReviewConfirmationValidationError(
                field_errors={"item": [str(exc)]}
            ) from exc
        except Exception:
            await self._session.rollback()
            raise

    async def _find_replay(
        self,
        *,
        context: WorkspaceContext,
        command: ConfirmImportReviewItemCommand,
    ) -> ImportReviewConfirmationResult | None:
        operation = await self._ledger.get_operation_by_idempotency_key(
            workspace_id=context.workspace.id,
            idempotency_key=command.idempotency_key,
        )
        if operation is None:
            return None
        if operation.idempotency_fingerprint != self._fingerprint(command):
            raise ImportReviewConfirmationConflictError(
                "Idempotency key was already used with another confirmation."
            )
        metadata = operation.extra_metadata or {}
        if (
            metadata.get("raw_transaction_id") != str(command.item_id)
            or metadata.get("uploaded_document_id") != str(command.document_id)
            or operation.status is not OperationStatus.CONFIRMED
        ):
            raise ImportReviewConfirmationConflictError(
                "The idempotent confirmation is no longer active."
            )
        return ImportReviewConfirmationResult(
            document_id=command.document_id,
            item_id=command.item_id,
            operation_id=operation.id,
            updated_item_ids=frozenset({command.item_id}),
            replayed=True,
        )

    @staticmethod
    def _fingerprint(command: ConfirmImportReviewItemCommand) -> str:
        payload = ":".join(
            (
                "confirm",
                str(command.document_id),
                str(command.item_id),
                command.operation_type.value,
                str(command.category_id),
                str(command.property_id) if command.property_id else "",
                "remember" if command.remember_rule else "no-rule",
                command.rule_pattern or "",
            )
        )
        return sha256(payload.encode()).hexdigest()
