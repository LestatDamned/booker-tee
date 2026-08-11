from typing import Literal
from uuid import UUID

from app.features.debts.domain import DebtKind
from app.features.ledger.domain.types import OperationType
from app.shared.schemas import ApplicationModel


class ManualOperationActivityDetails(ApplicationModel):
    payload_version: Literal[1] = 1
    display_label: str
    operation_type: OperationType


class ManualOperationCreatedActivityDetails(ManualOperationActivityDetails):
    pass


class ManualOperationUpdatedActivityDetails(ManualOperationActivityDetails):
    pass


class ManualOperationCancelledActivityDetails(ManualOperationActivityDetails):
    pass


class ManualOperationRestoredActivityDetails(ManualOperationActivityDetails):
    pass


class ManualOperationDeletedActivityDetails(ManualOperationActivityDetails):
    pass


class ImportReviewActivityDetails(ApplicationModel):
    payload_version: Literal[1] = 1
    document_id: UUID
    item_id: UUID
    affected_item_count: int = 1
    affected_document_count: int = 1


class ImportReviewItemConfirmedActivityDetails(ImportReviewActivityDetails):
    pass


class ImportReviewTransferCreatedActivityDetails(ImportReviewActivityDetails):
    pass


class ImportReviewOperationLinkedActivityDetails(ImportReviewActivityDetails):
    pass


class ImportReviewPostingUndoneActivityDetails(ImportReviewActivityDetails):
    pass


class ImportReviewOperationUnlinkedActivityDetails(ImportReviewActivityDetails):
    pass


class ImportedOperationUpdatedActivityDetails(ApplicationModel):
    payload_version: Literal[1] = 1


class DebtActivityDetails(ApplicationModel):
    payload_version: Literal[1] = 1
    display_label: str | None = None


class DebtCreatedActivityDetails(DebtActivityDetails):
    debt_kind: DebtKind


class DebtPaymentActivityDetails(DebtActivityDetails):
    payment_id: UUID


class DebtPaymentRecordedActivityDetails(DebtPaymentActivityDetails):
    pass


class DebtPaymentUndoneActivityDetails(DebtPaymentActivityDetails):
    pass


class DebtUpdatedActivityDetails(DebtActivityDetails):
    pass


class DebtArchivedActivityDetails(DebtActivityDetails):
    pass


class DebtRestoredActivityDetails(DebtActivityDetails):
    pass


class DebtDeletedActivityDetails(DebtActivityDetails):
    display_label: str


class DocumentUploadedActivityDetails(ApplicationModel):
    payload_version: Literal[1] = 1
    display_filename: str
