from uuid import UUID

from app.features.workspaces.activity_repository import WorkspaceActivityRepository
from app.features.workspaces.application.activity_details import (
    DebtActivityDetails,
    DebtArchivedActivityDetails,
    DebtCreatedActivityDetails,
    DebtDeletedActivityDetails,
    DebtPaymentRecordedActivityDetails,
    DebtPaymentUndoneActivityDetails,
    DebtRestoredActivityDetails,
    DebtUpdatedActivityDetails,
    DocumentUploadedActivityDetails,
    ImportedOperationUpdatedActivityDetails,
    ImportReviewItemConfirmedActivityDetails,
    ImportReviewOperationLinkedActivityDetails,
    ImportReviewOperationUnlinkedActivityDetails,
    ImportReviewPostingUndoneActivityDetails,
    ImportReviewTransferCreatedActivityDetails,
    ManualOperationActivityDetails,
    ManualOperationCancelledActivityDetails,
    ManualOperationCreatedActivityDetails,
    ManualOperationDeletedActivityDetails,
    ManualOperationRestoredActivityDetails,
    ManualOperationUpdatedActivityDetails,
)
from app.features.workspaces.domain.types import WorkspaceAuditEventType
from app.features.workspaces.service import WorkspaceContext
from app.shared.schemas import ApplicationModel


class WorkspaceActivityWriter:
    def __init__(self, repository: WorkspaceActivityRepository) -> None:
        self._repository = repository

    async def manual_operation_created(
        self,
        *,
        context: WorkspaceContext,
        operation_id: UUID,
        details: ManualOperationCreatedActivityDetails,
    ) -> None:
        await self._append_manual_operation(
            context=context,
            operation_id=operation_id,
            event_type=WorkspaceAuditEventType.MANUAL_OPERATION_CREATED,
            details=details,
        )

    async def manual_operation_updated(
        self,
        *,
        context: WorkspaceContext,
        operation_id: UUID,
        details: ManualOperationUpdatedActivityDetails,
    ) -> None:
        await self._append_manual_operation(
            context=context,
            operation_id=operation_id,
            event_type=WorkspaceAuditEventType.MANUAL_OPERATION_UPDATED,
            details=details,
        )

    async def manual_operation_cancelled(
        self,
        *,
        context: WorkspaceContext,
        operation_id: UUID,
        details: ManualOperationCancelledActivityDetails,
    ) -> None:
        await self._append_manual_operation(
            context=context,
            operation_id=operation_id,
            event_type=WorkspaceAuditEventType.MANUAL_OPERATION_CANCELLED,
            details=details,
        )

    async def manual_operation_restored(
        self,
        *,
        context: WorkspaceContext,
        operation_id: UUID,
        details: ManualOperationRestoredActivityDetails,
    ) -> None:
        await self._append_manual_operation(
            context=context,
            operation_id=operation_id,
            event_type=WorkspaceAuditEventType.MANUAL_OPERATION_RESTORED,
            details=details,
        )

    async def manual_operation_deleted(
        self,
        *,
        context: WorkspaceContext,
        operation_id: UUID,
        details: ManualOperationDeletedActivityDetails,
    ) -> None:
        await self._append_manual_operation(
            context=context,
            operation_id=operation_id,
            event_type=WorkspaceAuditEventType.MANUAL_OPERATION_DELETED,
            details=details,
        )

    async def import_review_item_confirmed(
        self,
        *,
        context: WorkspaceContext,
        operation_id: UUID,
        details: ImportReviewItemConfirmedActivityDetails,
    ) -> None:
        await self._append_import_review(
            context=context,
            operation_id=operation_id,
            event_type=WorkspaceAuditEventType.IMPORT_REVIEW_ITEM_CONFIRMED,
            details=details,
        )

    async def import_review_transfer_created(
        self,
        *,
        context: WorkspaceContext,
        operation_id: UUID,
        details: ImportReviewTransferCreatedActivityDetails,
    ) -> None:
        await self._append_import_review(
            context=context,
            operation_id=operation_id,
            event_type=WorkspaceAuditEventType.IMPORT_REVIEW_TRANSFER_CREATED,
            details=details,
        )

    async def import_review_operation_linked(
        self,
        *,
        context: WorkspaceContext,
        operation_id: UUID,
        details: ImportReviewOperationLinkedActivityDetails,
    ) -> None:
        await self._append_import_review(
            context=context,
            operation_id=operation_id,
            event_type=WorkspaceAuditEventType.IMPORT_REVIEW_OPERATION_LINKED,
            details=details,
        )

    async def import_review_posting_undone(
        self,
        *,
        context: WorkspaceContext,
        operation_id: UUID,
        details: ImportReviewPostingUndoneActivityDetails,
    ) -> None:
        await self._append_import_review(
            context=context,
            operation_id=operation_id,
            event_type=WorkspaceAuditEventType.IMPORT_REVIEW_POSTING_UNDONE,
            details=details,
        )

    async def import_review_operation_unlinked(
        self,
        *,
        context: WorkspaceContext,
        operation_id: UUID,
        details: ImportReviewOperationUnlinkedActivityDetails,
    ) -> None:
        await self._append_import_review(
            context=context,
            operation_id=operation_id,
            event_type=WorkspaceAuditEventType.IMPORT_REVIEW_OPERATION_UNLINKED,
            details=details,
        )

    async def imported_operation_updated(
        self,
        *,
        context: WorkspaceContext,
        operation_id: UUID,
        details: ImportedOperationUpdatedActivityDetails,
    ) -> None:
        await self._append_import_review(
            context=context,
            operation_id=operation_id,
            event_type=WorkspaceAuditEventType.IMPORTED_OPERATION_UPDATED,
            details=details,
        )

    async def debt_created(
        self,
        *,
        context: WorkspaceContext,
        debt_account_id: UUID,
        details: DebtCreatedActivityDetails,
    ) -> None:
        await self._append_debt(
            context, debt_account_id, WorkspaceAuditEventType.DEBT_CREATED, details
        )

    async def debt_payment_recorded(
        self,
        *,
        context: WorkspaceContext,
        debt_account_id: UUID,
        details: DebtPaymentRecordedActivityDetails,
    ) -> None:
        await self._append_debt(
            context,
            debt_account_id,
            WorkspaceAuditEventType.DEBT_PAYMENT_RECORDED,
            details,
        )

    async def debt_payment_undone(
        self,
        *,
        context: WorkspaceContext,
        debt_account_id: UUID,
        details: DebtPaymentUndoneActivityDetails,
    ) -> None:
        await self._append_debt(
            context,
            debt_account_id,
            WorkspaceAuditEventType.DEBT_PAYMENT_UNDONE,
            details,
        )

    async def debt_updated(
        self,
        *,
        context: WorkspaceContext,
        debt_account_id: UUID,
        details: DebtUpdatedActivityDetails,
    ) -> None:
        await self._append_debt(
            context, debt_account_id, WorkspaceAuditEventType.DEBT_UPDATED, details
        )

    async def debt_archived(
        self,
        *,
        context: WorkspaceContext,
        debt_account_id: UUID,
        details: DebtArchivedActivityDetails,
    ) -> None:
        await self._append_debt(
            context, debt_account_id, WorkspaceAuditEventType.DEBT_ARCHIVED, details
        )

    async def debt_restored(
        self,
        *,
        context: WorkspaceContext,
        debt_account_id: UUID,
        details: DebtRestoredActivityDetails,
    ) -> None:
        await self._append_debt(
            context, debt_account_id, WorkspaceAuditEventType.DEBT_RESTORED, details
        )

    async def debt_deleted(
        self,
        *,
        context: WorkspaceContext,
        debt_account_id: UUID,
        details: DebtDeletedActivityDetails,
    ) -> None:
        await self._append_debt(
            context, debt_account_id, WorkspaceAuditEventType.DEBT_DELETED, details
        )

    async def document_uploaded(
        self,
        *,
        context: WorkspaceContext,
        document_id: UUID,
        details: DocumentUploadedActivityDetails,
    ) -> None:
        await self._repository.append(
            workspace_id=context.workspace.id,
            event_type=WorkspaceAuditEventType.DOCUMENT_UPLOADED,
            actor_user_id=context.user.id,
            entity_type="uploaded_document",
            entity_id=document_id,
            details=details.model_dump(mode="json"),
        )

    async def _append_manual_operation(
        self,
        *,
        context: WorkspaceContext,
        operation_id: UUID,
        event_type: WorkspaceAuditEventType,
        details: ManualOperationActivityDetails,
    ) -> None:
        await self._repository.append(
            workspace_id=context.workspace.id,
            event_type=event_type,
            actor_user_id=context.user.id,
            entity_type="operation",
            entity_id=operation_id,
            details=details.model_dump(mode="json"),
        )

    async def _append_import_review(
        self,
        *,
        context: WorkspaceContext,
        operation_id: UUID,
        event_type: WorkspaceAuditEventType,
        details: ApplicationModel,
    ) -> None:
        await self._repository.append(
            workspace_id=context.workspace.id,
            event_type=event_type,
            actor_user_id=context.user.id,
            entity_type="operation",
            entity_id=operation_id,
            details=details.model_dump(mode="json"),
        )

    async def _append_debt(
        self,
        context: WorkspaceContext,
        debt_account_id: UUID,
        event_type: WorkspaceAuditEventType,
        details: DebtActivityDetails,
    ) -> None:
        await self._repository.append(
            workspace_id=context.workspace.id,
            event_type=event_type,
            actor_user_id=context.user.id,
            entity_type="debt",
            entity_id=debt_account_id,
            details=details.model_dump(mode="json", exclude_none=True),
        )
