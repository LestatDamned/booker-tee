"""Confirm imported income and expense rows from the review workflow."""

from hashlib import sha256
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.import_review.application.classification import (
    build_import_review_draft_evaluation,
)
from app.features.import_review.application.rules import ImportReviewRuleCreator
from app.features.import_review.domain.posting import (
    prepare_income_expense_posting,
    require_raw_transaction_account_id,
)
from app.features.import_review.errors import (
    ImportReviewConfirmationConflictError,
    ImportReviewConfirmationValidationError,
    RawTransactionReviewError,
)
from app.features.import_review.repository import ImportReviewRepository
from app.features.import_review.schemas.commands import (
    ConfirmImportReviewItemCommand,
    ImportReviewConfirmationResult,
)
from app.features.imports.documents.lifecycle import ImportedDocumentStatusUpdater
from app.features.imports.documents.repository import DocumentRepository
from app.features.imports.statements.types import RawTransactionStatus
from app.features.imports.statements.validation_service import StatementValidationService
from app.features.ledger.application.ledger_reference_resolver import LedgerReferenceResolver
from app.features.ledger.application.posting import LedgerPostingService
from app.features.ledger.domain.types import OperationStatus, OperationType
from app.features.ledger.errors import LedgerPostingError
from app.features.ledger.repository import LedgerRepository
from app.features.transaction_rules.domain.suggestions import rule_suggestion_auto_applies
from app.features.workspaces.activity_repository import WorkspaceActivityRepository
from app.features.workspaces.application.activity_details import (
    ImportReviewItemConfirmedActivityDetails,
)
from app.features.workspaces.application.activity_writer import WorkspaceActivityWriter
from app.features.workspaces.service import WorkspaceContext


class ImportReviewConfirmationActor:
    def __init__(self, session: AsyncSession) -> None:
        self._documents = DocumentRepository(session)
        self._review_repository = ImportReviewRepository(session)
        self._ledger = LedgerRepository(session)
        self._references = LedgerReferenceResolver(session)
        self._posting = LedgerPostingService(session)
        self._rule_creator = ImportReviewRuleCreator(session)

    async def apply(
        self,
        *,
        context: WorkspaceContext,
        command: ConfirmImportReviewItemCommand,
    ) -> ImportReviewConfirmationResult:
        row = await self._review_repository.get_raw_transaction_for_workspace(
            context.workspace.id,
            command.document_id,
            command.item_id,
        )
        if row is None:
            raise RawTransactionReviewError("Raw transaction row was not found.")

        replay = await self.find_replay(context=context, command=command)
        if replay is not None:
            return replay
        document = await self._documents.get_document_for_workspace_for_update(
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
        if command.operation_type is not None and command.operation_type not in {
            OperationType.INCOME,
            OperationType.EXPENSE,
        }:
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

        category = await self._references.get_category_or_uncategorized(
            context.workspace.id,
            command.category_id,
        )
        suggested_property_id = (
            row.suggested_property_id if rule_suggestion_auto_applies(row) else None
        )
        property_ = await self._references.get_property(
            context.workspace.id,
            command.property_id or suggested_property_id,
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
            await self._review_repository.has_confirmed_raw_transaction_with_dedupe_hash(
                workspace_id=context.workspace.id,
                dedupe_hash=row.dedupe_hash,
                exclude_raw_transaction_id=row.id,
            )
        ):
            raise ImportReviewConfirmationConflictError(
                "A confirmed raw transaction already uses this dedupe hash."
            )

        account_id = require_raw_transaction_account_id(row)
        account = await self._references.get_account(context.workspace.id, account_id)
        plan = prepare_income_expense_posting(row, account)
        await self._references.ensure_income_expense_account(
            context.workspace.id,
            account,
            plan.operation_type,
        )
        operation = await self._posting.post_imported_income_expense(
            context=context,
            document_id=command.document_id,
            raw_transaction_id=row.id,
            account=account,
            plan=plan,
            category=category,
            property_=property_,
            idempotency_key=command.idempotency_key,
            idempotency_fingerprint=self.fingerprint(command),
        )
        await self._review_repository.link_raw_transaction_to_operation(
            row,
            operation_id=operation.id,
        )
        updated_item_ids: set[UUID] = {command.item_id}
        if command.remember_rule:
            summary = await self._rule_creator.create_and_apply(
                context=context,
                document_id=command.document_id,
                item_id=command.item_id,
                category_id=command.category_id,
                property_id=command.property_id,
                pattern=command.rule_pattern,
            )
            updated_item_ids.update(summary.updated_raw_transaction_ids)
        await StatementValidationService(self._documents).refresh_for_document(document)
        await ImportedDocumentStatusUpdater(self._documents).sync_review_status(document)
        return ImportReviewConfirmationResult(
            document_id=command.document_id,
            item_id=command.item_id,
            operation_id=operation.id,
            updated_item_ids=frozenset(updated_item_ids),
            replayed=False,
        )

    async def find_replay(
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
        if operation.idempotency_fingerprint != self.fingerprint(command):
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
    def fingerprint(command: ConfirmImportReviewItemCommand) -> str:
        payload = ":".join(
            (
                "confirm",
                str(command.document_id),
                str(command.item_id),
                command.operation_type.value if command.operation_type is not None else "",
                str(command.category_id),
                str(command.property_id) if command.property_id else "",
                "remember" if command.remember_rule else "no-rule",
                command.rule_pattern or "",
            )
        )
        return sha256(payload.encode()).hexdigest()


class ImportReviewConfirmationService:
    def __init__(
        self,
        session: AsyncSession,
        actor: ImportReviewConfirmationActor | None = None,
    ) -> None:
        self._session = session
        self._actor = actor or ImportReviewConfirmationActor(session)
        self._activity = WorkspaceActivityWriter(WorkspaceActivityRepository(session))

    async def execute(
        self,
        *,
        context: WorkspaceContext,
        command: ConfirmImportReviewItemCommand,
    ) -> ImportReviewConfirmationResult:
        try:
            result = await self._actor.apply(context=context, command=command)
            if not result.replayed:
                await self._activity.import_review_item_confirmed(
                    context=context,
                    operation_id=result.operation_id,
                    details=ImportReviewItemConfirmedActivityDetails(
                        document_id=result.document_id,
                        item_id=result.item_id,
                        affected_item_count=len(result.updated_item_ids),
                    ),
                )
            await self._session.commit()
            return result
        except IntegrityError as exc:
            await self._session.rollback()
            replay = await self._actor.find_replay(context=context, command=command)
            if replay is not None:
                return replay
            raise ImportReviewConfirmationConflictError(
                "Import review confirmation conflicts with committed data."
            ) from exc
        except LedgerPostingError as exc:
            await self._session.rollback()
            raise ImportReviewConfirmationValidationError(
                field_errors={"item": [str(exc)]}
            ) from exc
        except Exception:
            await self._session.rollback()
            raise
