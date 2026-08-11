from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field

from app.features.ledger.domain.types import OperationSource
from app.features.ledger.schemas.manual import ManualOperationReadDto
from app.shared.schemas import ApplicationModel


class ImportOperationProvenanceDto(ApplicationModel):
    kind: Literal["import"] = "import"
    uploaded_document_id: UUID | None
    raw_transaction_id: UUID | None


class DebtOperationProvenanceDto(ApplicationModel):
    kind: Literal["debt"] = "debt"
    debt_account_id: UUID | None


class SystemOperationProvenanceDto(ApplicationModel):
    kind: Literal["system"] = "system"


OperationProvenanceDto = Annotated[
    ImportOperationProvenanceDto | DebtOperationProvenanceDto | SystemOperationProvenanceDto,
    Field(discriminator="kind"),
]


class OperationCapabilitiesDto(ApplicationModel):
    can_edit: bool = False
    edit_kind: Literal["manual", "imported", "none"] = "none"
    can_cancel: bool = False
    can_restore: bool = False
    can_delete: bool = False
    readonly_reason: (
        Literal[
            "financial_write_forbidden",
            "operation_state_readonly",
            "source_workflow_required",
            "system_operation",
        ]
        | None
    ) = None


class OperationReadDto(ManualOperationReadDto):
    source: OperationSource
    provenance: OperationProvenanceDto | None
    capabilities: OperationCapabilitiesDto
